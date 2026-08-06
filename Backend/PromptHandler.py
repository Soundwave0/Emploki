#Handles the prompting of the LLM and the retrieval of the response.
import ollama
import json
import requests
from bs4 import BeautifulSoup

#initialize the model and configure
class  PromptHandler:
    def __init__(self, model:str = "codellama:7b-instruct", resume_data_path:str = "/Configs/resume_data.json", resume_template_path:str = "/Configs/resume_template.txt",job_offer_url:str):
        self.model = model
        self.resume_data_path = resume_data_path
        self.resume_template_path = resume_template_path
        self.job_offer_url = job_offer_url

    def dump_job_requirements(self)->str:
        response = requests.get(self.job_offer_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())
        return clean_text

    def generate_resume(self)->str | None: 
        client = ollama.Client()
        with open(self.resume_template_path, 'r', encoding='utf-8') as file:
            tex_content = file.read()
        prompt_construction = ["Using the following JSON information about the person trying to generate a resume:",json.load(open(self.resume_data_path)),
                  "The following information about the job offer listing:",self.dump_job_requirements(),
                  "Use the following latex code template when writing the latex code:",tex_content]
        prompt = " ".join(prompt_construction)
        # ensure this works
        response = client.generate(model=self.model, prompt=prompt)
        return response.response