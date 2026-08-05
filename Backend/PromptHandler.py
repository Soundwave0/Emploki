#Handles the prompting of the LLM and the retrieval of the response.
import ollama
import json

#initialize the model and configure
class  PromptHandler:
    def __init__(self, model:str = "codellama:7b-instruct", resume_data_path:str = "/Configs/resume_data.json", resume_template_path:str = "/Configs/resume_template.txt"):
        self.model = model
        self.resume_data_path = resume_data_path
        self.resume_template_path = resume_template_path
    def dump_job_requirements(self):
        #go through job offer page dump the html and feed through the LLM to extract the requirements


    def generate_resume(self)->str | None: 
        client = ollama.Client()
        prompt = ("Using the following JSON information about the person trying to generate a resume " + json.load(open(self.resume_data_path)))  # ensure this works
        response = client.generate(model=self.model, prompt=prompt)
        return response.response