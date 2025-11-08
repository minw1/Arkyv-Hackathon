from pdfminer.high_level import extract_text
import pickle
import os
import re


if not os.path.exists("bbr.pkl"):
    text = extract_text('byggregler.pdf')
    with open("bbr.pkl", "wb") as file:
        pickle.dump(text, file)
else:
    with open("bbr.pkl", "rb") as file:
        text = pickle.load(file)

parts = re.split(r'\n(?=\d+:\d+)', text)

if not os.path.exists("chunks.pkl"):
    with open("chunks.pkl", "wb") as file:
        pickle.dump(parts, file)

