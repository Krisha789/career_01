# CareerCraft AI – AI-Based Personalized Career Content Generator

Stack: Python, Streamlit, Google Gemini API, SQLite, python-docx.

Pages: **Home** (landing), **Create** (generator), **History** (search, download, delete).

## Run
```bash
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"     # or put it in .streamlit/secrets.toml, or type it in the sidebar
streamlit run app.py
```
Free API key: https://aistudio.google.com

## Deploy
Push to GitHub (include the `.streamlit/config.toml` theme file), then deploy on Streamlit Community Cloud and add GEMINI_API_KEY under Secrets.
