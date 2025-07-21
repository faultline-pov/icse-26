import openai
from openai import OpenAI

import time
import os

class OpenAIEmbed:

    def __init__(self, model):

        self.model = model
        self.client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])

    def embed(self, text):

        from models import ModelException

        count = 0
        while True:
            try:
                embedding = self.client.embeddings.create(input=text, model=self.model)["data"][0]["embedding"]
                break
            except openai.InvalidRequestError as e:
                raise ModelException(f"Encountered an error with OpenAI API {e}")
            except (openai.RateLimitError, openai.ServiceUnavailableError, openai.APIError):
                count += 1
                if count >= 5:
                    raise ModelException("Too many retries")
                print("OpenAI Error. Waiting 10 seconds and retrying")
                time.sleep(10)
            except:
                raise ModelException("Unknown error")

        return embedding