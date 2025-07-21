import openai
from openai import OpenAI
import os

import time
import os

class OpenAIGen:

    def __init__(self, model):

        self.model = model
        self.client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

    def __str__(self):
        return self.model

    def gen(self, messages, temperature=0, seed=True, top_k=1, cache=False):
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
            raise ModelException("Top k sampling requires a non-zero temperature")

        count = 0
        while True:
            try:
                if seed:
                    chat = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, seed=42, n=top_k)
                else:
                    chat = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature, n=top_k)   
                break
            except openai.BadRequestError as e:
                raise ModelException(f"Encountered an error with OpenAI API {e}")
            except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError, openai.ConflictError, openai.InternalServerError, openai.UnprocessableEntityError):
                count += 1
                if count >= 5:
                    raise ModelException("OpenAI API: Too many retries")
                print("OpenAI Rate Limit Error. Waiting 10 seconds and retrying")
                time.sleep(10)
            except:
                raise ModelException("OpenAI API: Unknown error")

        return [choice.message.content for choice in chat.choices]
