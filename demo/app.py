import sys
import os

# VERY IMPORTANT
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import pandas as pd

from parser.parse_edi import parse_edi_text, save_output_json

st.title("EDI Parser Demo (835 + 837)")

file = st.file_uploader("Upload EDI file")

if file:
    if st.button("Process"):
        text = file.getvalue().decode("utf-8", errors="ignore")

        result = parse_edi_text(text, file.name)

        if result["status"] == "error":
            st.error(result["message"])
            st.stop()

        st.success("Parsed Successfully")

        st.write("File Type:", result["file_type"])
        st.json(result)

        # Save output
        output_path = save_output_json(result, file.name, "output")
        st.write("Saved at:", output_path)