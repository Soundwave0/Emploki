#Handles the prompting of the LLM and the retrieval of the response.
import ollama
import json
from bs4 import BeautifulSoup
import os
import subprocess
import shutil
from typing import Optional, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException


DEFAULT_PAGE_LOAD_TIMEOUT = 30
# Generation on local CPU/GPU hardware can take several minutes for a full resume.
DEFAULT_OLLAMA_TIMEOUT = 600
# A complete resume template can exceed 2,048 tokens; leave enough room for
# \end{document} while the client timeout still bounds the total wait.
MAX_GENERATED_TOKENS = 4096
LATEX_SYSTEM_PROMPT = r"""
You are a LaTeX resume generator. Return only one complete, compilable LaTeX
document: start with \documentclass and end with \end{document}. Use the
provided template as the structural basis and fill it with the supplied resume
data tailored to the job listing. Do not explain the template, summarize the
resume, add Markdown fences, or write any text outside the LaTeX source.
""".strip()

#initialize the model and configure
class PromptHandler:
    def __init__(self, job_offer_url: str, model: str = "codellama:7b-instruct",
                 resume_data_path: str = "Configs\\resume_data.json",
                 resume_template_path: str = "Configs\\resume_template.txt",
                 job_offer_text: Optional[str] = None,
                 page_load_timeout: int = DEFAULT_PAGE_LOAD_TIMEOUT,
                 ollama_timeout: int = DEFAULT_OLLAMA_TIMEOUT):
        self.model = model
        self.resume_data_path = resume_data_path
        self.resume_template_path = resume_template_path
        self.job_offer_url = job_offer_url
        self.job_offer_text = job_offer_text
        self.page_load_timeout = page_load_timeout
        self.ollama_timeout = ollama_timeout

    def dump_job_requirements(self) -> str:
        if self.job_offer_text:
            return self.job_offer_text

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(self.page_load_timeout)

        try:
            try:
                driver.get(self.job_offer_url)
            except TimeoutException as exc:
                raise RuntimeError(
                    f"The job page did not finish loading within {self.page_load_timeout} seconds."
                ) from exc

            # Get page source after JavaScript execution
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            clean_text = ' '.join(soup.get_text().split())
            return clean_text
        finally:
            driver.quit()

    def generate_resume_str(self) -> Optional[str]:
        client = ollama.Client(timeout=self.ollama_timeout)
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
        response = client.generate(
            model=self.model,
            prompt=prompt,
            system=LATEX_SYSTEM_PROMPT,
            stream=False,
            options={"num_predict": MAX_GENERATED_TOKENS},
        )
        return self._latex_source(self._response_text(response))

    @staticmethod
    def _response_text(response) -> str:
        """Extract generated text from Ollama's object or dictionary response."""
        text = response.get("response") if isinstance(response, dict) else getattr(response, "response", None)
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(
                "Ollama returned no generated text. Check that the selected model is installed and running."
            )
        return text

    @staticmethod
    def _latex_source(text: str) -> str:
        """Extract a full LaTeX document and reject prose-only model replies."""
        start = text.find("\\documentclass")
        end_marker = "\\end{document}"
        end = text.rfind(end_marker)
        if start == -1 or end == -1 or end < start:
            raise RuntimeError(
                "Ollama returned an explanation instead of a complete LaTeX document. "
                "Try the generation again or use a model better suited to code generation."
            )
        return text[start:end + len(end_marker)].strip()

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
        client = ollama.Client(timeout=self.ollama_timeout)
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
            "generate only the code which would compile"
        ]
        prompt = " ".join(prompt_construction)
        response = client.generate(
            model=self.model,
            prompt=prompt,
            system=LATEX_SYSTEM_PROMPT,
            stream=False,
            options={"num_predict": MAX_GENERATED_TOKENS},
        )
        latex_output = self._latex_source(self._response_text(response))

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
