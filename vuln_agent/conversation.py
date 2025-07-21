import litellm
from litellm import get_max_tokens, token_counter
from vuln_agent.helpers import *

class Conversation:
    def __init__(self, model, logger, temperature=0.0, budget=5.0, timeout=3600):
        self.model = model
        self.messages = []
        self.max_tokens = get_max_tokens(str(self.model))
        self.threshold = int(0.20 * self.max_tokens)
        self.fraction_to_condense = 0.7
        self.logger = logger
        self.budget = budget
        self.timeout = timeout
        self.temperature = temperature
    
    def add_message(self, role, content):
        if role == "assistant":
            raise ValueError("Role 'assistant' is reserved for model responses.")

        cost, time = self.logger.get_cost_and_time()
        if cost >= self.budget:
            self.logger.log_failure(f"Exceeded budget of ${self.budget:.2f}. Current cost: ${cost:.2f}")
            raise RuntimeError(f"Exceeded budget of ${self.budget:.2f}. Current cost: ${cost:.2f}")
        elif time >= self.timeout:
            self.logger.log_failure(f"Exceeded timeout of {self.timeout} seconds. Current time: {time} seconds")
            raise RuntimeError(f"Exceeded timeout of {self.timeout} seconds. Current time: {time} seconds")
            
        self.messages.append({"role": role, "content": content})
        num_tokens = token_counter(model=str(self.model), messages=self.messages)
        if num_tokens >= self.threshold:
            self.condense()
    
    def generate(self):
        response = self.model.gen(self.messages, top_k=1, temperature=self.temperature, cache=True)[0]
        self.messages.append({"role": "assistant", "content": response})
        return response

    def condense(self):
        self.logger.log_status("Condensing conversation to reduce token count.")
        total_tokens = token_counter(model=str(self.model), messages=self.messages)
        self.logger.log_status(f"Current conversation length: {len(self.messages)} messages, {total_tokens} tokens.")
        messages_to_condense = []
        messages_to_retain = []
        for i, message in enumerate(self.messages):
            messages_to_condense.append(message)
            if token_counter(model=str(self.model), messages=messages_to_condense) >= total_tokens * self.fraction_to_condense:
                messages_to_condense.pop()  # Remove the last message to condense
                messages_to_retain = self.messages[i:]
                break

        prompt = """You are maintaining a context-aware state summary for an interactive agent.
You will be given a list of events corresponding to actions taken by the agent. Track:
FILES READ:
(List of relevant files read by the agent, and a brief summary of each file)
FILES MODIFIED:
(List of files modified by the agent, and a brief summary of each modification)
CODE SUMMARY:
(Brief summary of the understanding gathered by the agent about the functionality and structure of the code)
CODE STATE:
(Brief summary of the current state of the code - does it compile, does it run, etc.)
COMPLETED:
(Tasks completed so far, with brief results)
PENDING:
(Tasks that still need to be done)
"""
        prompt += "\n\n"

        for i, message in enumerate(messages_to_condense):
            prompt += f"<EVENT id={i} role=({message['role'].upper()})>\n{message['content']}\n</EVENT>\n"

        prompt += ("Now summarize the events in the format shown above. Make sure to generate each of the following:\n"
                   "FILES READ, FILES MODIFIED, CODE SUMMARY, CODE STATE, COMPLETED, PENDING.\n")

        condensation_conversation = [
            {"role": "system", "content": "You are an intelligent code assistant."},
            {"role": "user", "content": prompt}
        ]
        condensation = self.model.gen(condensation_conversation, top_k=1, temperature=0, cache=False)[0]

        new_messages = [
            {
                "role": "user",
                "content": "I am truncating the conversation to minimize cost. Summarize what you have done so far."
            },
            {
                "role": "assistant",
                "content": condensation
            }
        ]
        self.logger.log_output(condensation)
        # Keep the initial few exchanges unchanged
        assert self.messages[0]["role"] == "system" and self.messages[1]["role"] == "user"
        self.messages = self.messages[:2] + new_messages + messages_to_retain
        self.logger.log_status(f"Retained first 2 messages and last {len(messages_to_retain)} messages.")
        new_tokens = token_counter(model=str(self.model), messages=self.messages)
        self.logger.log_status(f"New conversation length: {len(self.messages)} messages, {new_tokens} tokens.")