# How to use this file

1. Rename `app_mesa_streamlit.py` to `app.py`.
2. Put it in the root of the GitHub repository.
3. Make sure the repository contains the `dvm_abm/` package created earlier.
4. Make sure `requirements.txt` contains at least:

streamlit
mesa
pandas
numpy
matplotlib
plotly
pyyaml
openpyxl
statsmodels

5. Run locally:

streamlit run app.py

6. In Streamlit Community Cloud, set main file path to:

app.py
