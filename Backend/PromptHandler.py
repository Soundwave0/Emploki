#Handles the prompting of the LLM and the retrieval of the response.
import ollama
import json
import requests
from bs4 import BeautifulSoup
import os
import subprocess
import shutil
from typing import Optional, Tuple

#initialize the model and configure
class PromptHandler:
    def __init__(self, job_offer_url: str, model: str = "codellama:7b-instruct",
                 resume_data_path: str = "Configs\\resume_data.json",
                 resume_template_path: str = "Configs\\resume_template.txt"):
        self.model = model
        self.resume_data_path = resume_data_path
        self.resume_template_path = resume_template_path
        self.job_offer_url = job_offer_url

    def dump_job_requirements(self) -> str:
        response = requests.get(self.job_offer_url)
        soup = BeautifulSoup(response.content, 'html.parser')
        clean_text = ' '.join(soup.get_text().split())
        return clean_text

    def generate_resume_str(self) -> Optional[str]:
        client = ollama.Client()
        with open(self.resume_template_path, 'r', encoding='utf-8') as file:
            tex_content = file.read()
        with open(self.resume_data_path, 'r', encoding='utf-8') as f:
            resume_data = json.load(f)
        prompt_construction = [
            "Using the following JSON information about the person trying to generate a resume:",
            json.dumps(resume_data),
            "The following information about the job offer listing:",
            self.dump_job_requirements(),
            "Use the following latex code template when writing the latex code:",
            tex_content,
        ]
        prompt = " ".join(prompt_construction)
        response = client.generate(model=self.model, prompt=prompt)
        return getattr(response, "response", None)

    def save_tex(self, latex_str: str, out_path: str) -> str:
        # ensure directory exists
        directory = os.path.dirname(out_path) or "."
        os.makedirs(directory, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(latex_str)
        return out_path
#Fix the following function thoroughly
    def compile_with_pandoc(self, tex_path: str, pdf_path: str, pdf_engine: str = "xelatex") -> Tuple[bool, str]:
        """Compile a .tex file to PDF using pandoc. Returns (success, message).
        Requires pandoc and a TeX engine installed and available in PATH.
        """
        if shutil.which("pandoc") is None:
            return False, "pandoc not found in PATH"
        cmd = ["pandoc", tex_path, "-s", "-o", pdf_path, f"--pdf-engine={pdf_engine}"]
        try:
            proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True, proc.stdout or "PDF created"
        except subprocess.CalledProcessError as e:
            return False, e.stderr or str(e)

    def generate_resume_latex(self, output_tex_path: str = "output.tex",
                              output_pdf_path: Optional[str] = None,
                              pdf_engine: str = "xelatex",
                              compile_pdf: bool = True) -> Tuple[str, Optional[str]]:
        """Generate LaTeX using the LLM, save it to output_tex_path, and optionally compile to PDF.

        Returns a tuple (tex_path, pdf_path_or_None).
        """
        client = ollama.Client()
        with open(self.resume_template_path, 'r', encoding='utf-8') as file:
            tex_content = file.read()
        with open(self.resume_data_path, 'r', encoding='utf-8') as f:
            resume_data = json.load(f)
        prompt_construction = [
            "Using the following JSON information about the person trying to generate a resume:",
            json.dumps(resume_data),
            "The following information about the job offer listing:",
            self.dump_job_requirements(),
            "Use the following latex code template when writing the latex code:",
            tex_content,
        ]
        prompt = " ".join(prompt_construction)
        response = client.generate(model=self.model, prompt=prompt)
        latex_output = getattr(response, "response", "")

        # save the LaTeX to file
        tex_path = self.save_tex(latex_output, output_tex_path)

        pdf_path = None
        if compile_pdf:
            if output_pdf_path is None:
                output_pdf_path = os.path.splitext(tex_path)[0] + ".pdf"
            ok, msg = self.compile_with_pandoc(tex_path, output_pdf_path, pdf_engine=pdf_engine)
            if not ok:
                raise RuntimeError(f"Pandoc compile failed: {msg}")
            pdf_path = output_pdf_path

        return tex_path, pdf_path
