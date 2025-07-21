import time
import os
import google.generativeai as genai

class GoogleGen:

    def __init__(self, model):

        genai.configure(api_key=os.environ['GOOGLE_API_KEY'])
        self.model = model
        self.model_obj = genai.GenerativeModel(model)

    def __str__(self):
        return self.model
    
    def gen(self, messages, temperature=0, top_k=1):
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

        remap = lambda x: 'model' if (x == 'assistant') else x
        new_messages = [{'role': remap(message['role']),
                        'parts': [message['content']]}
                        for message in messages if message['role'] != 'system'
                        ]
        retry_count = 0
        while True:
            try:
                response = self.model_obj.generate_content(new_messages,
                                generation_config=genai.types.GenerationConfig(
                                                            candidate_count=1, # Gemini doesn't yet support multiple candidates
                                                            temperature=temperature))
                
                if any(len(candidate.content.parts) > 1 for candidate in response.candidates):
                    raise ModelException("Gemini returned multi-part candidates")
                elif any(len(candidate.content.parts) == 0 for candidate in response.candidates):
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason == 3:
                        raise ModelException("Gemini flagged this for safety reasons")
                    elif finish_reason == 4:
                        raise ModelException("Gemini flagged this for recitation reasons")
                    else:
                        raise ModelException(f"Gemini returned no candidates. Finish reason: {finish_reason}")
                break
            except Exception as e:
                retry_count += 1
                if retry_count >= 5:
                    raise ModelException(f"Google API Error: {e}")
                if "safety reasons" in str(e):
                    raise ModelException("Gemini flagged this for safety reasons")
                if "recitation reasons" in str(e):
                    raise ModelException("Gemini flagged this for recitation reasons")
                if "Resource has been exhausted" in str(e):
                    print(f"Google API Error: {e}. Waiting 10 seconds and retrying")
                else:
                    raise ModelException(f"Google API Error: {e}")
                time.sleep(10)
        
        assert len(response.candidates) == 1
        this_gen = [response.candidates[0].content.parts[0].text]

        if top_k > 1:
            return this_gen + self.gen(messages, temperature, top_k=top_k-1)
        else:
            return this_gen
