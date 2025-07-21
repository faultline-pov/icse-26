import time
from datetime import datetime
import os
import requests
import litellm
from litellm import completion, completion_cost

class ClaudeGen:

    def __init__(self, model, logger):

        self.api_key=os.environ['ANTHROPIC_API_KEY']
        self.model = model
        self.logger = logger
    
    def __str__(self):
        return self.model
    
    def gen(self, messages, temperature=0, top_k=1, cache=False):
        '''
        messages: [{'role': 'system', 'content': 'You are an intelligent code assistant'},
                   {'role': 'user', 'content': 'Translate this program...'},
                   {'role': 'assistant', 'content': 'Here is the translation...'},
                   {'role': 'user', 'content': 'Do something else...'}]
                   
        <returned>: ['Sure, here is...',
                     'Okay, let me see...',
                     ...]
        len(<returned>) == top_k
        '''
        
        from .. import ModelException

        if top_k != 1 and temperature == 0:
            self.logger.log_failure("Top k sampling requires a non-zero temperature")
            raise ModelException("Top k sampling requires a non-zero temperature")
        
        if cache:
            cached_messages = [{
                    'role': message['role'],
                    'content': [{
                        'type': 'text',
                        'text': message['content'],
                        'cache_control': {'type': 'ephemeral'}
                    }]
                } for message in messages[:4]] + messages[4:]
                 # Anthropic allows prompt caching for up to 4 message blocks only
            messages = cached_messages

        start_time = time.time()
        start_time_str = f"{datetime.now()}"
        retry_count = 0
        while True:
            try:
                response = completion(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    top_k=top_k,
                    api_key=self.api_key,
                    max_tokens=64000,
                )
                break
            except (litellm.BadRequestError, litellm.AuthenticationError,
                    litellm.NotFoundError, litellm.UnprocessableEntityError) as e:
                self.loadr.log_failure(f"Error in litellm: {e}")
                raise ModelException(f"Error in litellm: {e}")
            except (litellm.Timeout, litellm.RateLimitError, litellm.InternalServerError, litellm.APIConnectionError):
                retry_count += 1
                if retry_count > 5:
                    self.logger.log_failure("Max retries exceeded for Claude API")
                    raise ModelException("Max retries exceeded for Claude API")
                time.sleep(2 ** retry_count)
            except Exception as e:
                self.logger.log_failure(f"Unexpected error: {e}")
                raise ModelException(f"Unexpected error: {e}")

        elapsed_time = time.time() - start_time
        if 'prompt_tokens_details' in response['usage']:
            cached_tokens = response['usage']['prompt_tokens_details'].cached_tokens
        else:
            cached_tokens = 0

        cost = completion_cost(completion_response=response, model=self.model)

        self.logger.log_action({'type': 'llm_call',
                                'input_tokens': response['usage']['prompt_tokens'],
                                'cached_tokens': cached_tokens,
                                'output_tokens': response['usage']['completion_tokens'],
                                'cost': cost,
                                'start_time': start_time_str,
                                'elapsed_time': elapsed_time})

        return [response['choices'][i]['message']['content'] for i in range(len(response['choices']))]

