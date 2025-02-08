import os
import re
import json
import sqlite3
import argparse
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import shutil
import cv2
import numpy as np
from PIL import Image
from pdf2image import convert_from_path

# Ensure Tesseract is installed
if not shutil.which("tesseract"):
    raise RuntimeError("Tesseract is not installed. Install it from https://github.com/UB-Mannheim/tesseract/wiki")

class FormProcessor:
    def __init__(self):
        self.difficulty_tasks = [
            "bending_or_stooping", "putting_on_shoes", "sleeping",
            "standing_for_an_hour", "stairs", "walking_through_store",
            "driving", "preparing_meal", "yard_work", "picking_up_items"
        ]
        self.pain_symptoms = ["pain", "numbness", "tingling", "burning", "tightness"]

    def enhance_image(self, image):
        """Improve OCR accuracy by converting to grayscale, applying blur, and thresholding."""
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blurred, 128, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary)

    def extract_text(self, file_path):
        """Extract text from a PDF or image."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File '{file_path}' not found.")

        text = ""
        if file_path.lower().endswith('.pdf'):
            images = convert_from_path(file_path)
            for img in images:
                processed_img = self.enhance_image(img)
                text += pytesseract.image_to_string(processed_img)
        else:
            img = Image.open(file_path)
            processed_img = self.enhance_image(img)
            text = pytesseract.image_to_string(processed_img)

        return text.strip()

    def parse_ocr_output(self, text):
        """Extract structured data from OCR text."""
        return {
            "patient_details": self._extract_patient_info(text),
            "treatment_details": self._extract_treatment_info(text),
            "difficulty_ratings": self._extract_difficulty_ratings(text),
            "patient_changes": self._extract_patient_changes(text),
            "pain_symptoms": self._extract_pain_symptoms(text),
            "medical_assistant_data": self._extract_ma_data(text)
        }

    def _extract_patient_info(self, text):
        return {
            "patient_name": self._find_value(r"Patient Name\s*:\s*(.*)", text),
            "dob": self._find_value(r"DOB\s*:\s*(.*)", text)
        }

    def _extract_treatment_info(self, text):
        return {
            "date": self._find_value(r"Date\s*:\s*(.*)", text),
            "injection": self._find_checkbox(r"INJECTION\s*:\s*(YES|NO)", text),
            "exercise_therapy": self._find_checkbox(r"Exercise Therapy\s*:\s*(YES|NO)", text)
        }

    def _extract_difficulty_ratings(self, text):
        return {task: self._find_numeric_value(rf"{task.replace('_', ' ').title()}:\s*([0-5])", text) for task in self.difficulty_tasks}

    def _extract_patient_changes(self, text):
        return {
            "since_last_treatment": self._find_value(r"Patient changes since last treatment:(.*?)(?=\n\S)", text, True),
            "since_start_of_treatment": self._find_value(r"Patient changes since the start of treatment:(.*?)(?=\n\S)", text, True),
            "last_3_days": self._find_value(r"Describe any functional changes within the last three days \(good or bad\):(.*)", text)
        }

    def _extract_pain_symptoms(self, text):
        return {symptom: self._find_numeric_value(rf"{symptom.title()}:\s*([0-9]{{1,2}})", text) for symptom in self.pain_symptoms}

    def _extract_ma_data(self, text):
        return {
            "blood_pressure": self._find_value(r"Blood Pressure\s*:\s*(.*)", text),
            "hr": self._find_numeric_value(r"HR\s*:\s*(\d+)", text),
            "weight": self._find_numeric_value(r"Weight\s*:\s*(\d+)", text),
            "height": self._find_value(r"Height\s*:\s*(.*)", text),
            "spo2": self._find_numeric_value(r"SpO2\s*:\s*(\d+)", text),
            "temperature": self._find_value(r"Temperature\s*:\s*(.*)", text),
            "blood_glucose": self._find_numeric_value(r"Blood Glucose\s*:\s*(\d+)", text),
            "respirations": self._find_numeric_value(r"Respirations\s*:\s*(\d+)", text)
        }

    def _find_value(self, pattern, text, dotall=False):
        match = re.search(pattern, text, re.DOTALL if dotall else 0)
        return match.group(1).strip() if match else None

    def _find_numeric_value(self, pattern, text):
        match = re.search(pattern, text)
        return int(match.group(1)) if match else None

    def _find_checkbox(self, pattern, text):
        match = re.search(pattern, text)
        return match.group(1) if match else None

class DatabaseManager:
    def __init__(self, db_path='patients.db'):
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                dob TEXT
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS forms_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                form_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(patient_id) REFERENCES patients(id)
            )
        ''')
        self.conn.commit()

    def insert_data(self, data):
        cur = self.conn.cursor()
        cur.execute('INSERT INTO patients (name, dob) VALUES (?, ?)',
                    (data['patient_details'].get('patient_name', 'Unknown'), data['patient_details'].get('dob', 'Unknown')))
        patient_id = cur.lastrowid
        cur.execute('INSERT INTO forms_data (patient_id, form_json) VALUES (?, ?)',
                    (patient_id, json.dumps(data)))
        self.conn.commit()
        return patient_id

def process_file(input_path, output_json='output.json'):
    processor = FormProcessor()
    db = DatabaseManager()
    
    text = processor.extract_text(input_path)
    data = processor.parse_ocr_output(text)

    with open(output_json, 'w') as f:
        json.dump(data, f, indent=2)
    
    db.insert_data(data)
    print(f"✅ Data processed and saved to {output_json} and database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process patient assessment forms")
    parser.add_argument('input_file', help="Path to PDF or image file")
    parser.add_argument('--output', default='output.json', help="Output JSON path")
    args = parser.parse_args()

    process_file(args.input_file, args.output)

# import re
# import json
# import sqlite3
# from pathlib import Path
# from PIL import Image
# import pytesseract
# from pdf2image import convert_from_path

# # Configure Tesseract path if necessary
# # pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

# class FormProcessor:
#     def __init__(self):
#         self.difficulty_tasks = [
#             "bending_or_stooping",
#             "putting_on_shoes",
#             "sleeping",
#             "standing_for_an_hour",
#             "stairs",
#             "walking_through_store",
#             "driving",
#             "preparing_meal",
#             "yard_work",
#             "picking_up_items"
#         ]
        
#         self.pain_symptoms = [
#             "pain",
#             "numbness",
#             "tingling",
#             "burning",
#             "tightness"
#         ]

#     def preprocess_image(self, image):
#         """Convert to grayscale and apply thresholding."""
#         return image.convert('L').point(lambda x: 0 if x < 128 else 255, '1')

#     def extract_text(self, file_path):
#         """Handle both PDF and image files."""
#         if file_path.lower().endswith('.pdf'):
#             images = convert_from_path(file_path)
#             text = ""
#             for img in images:
#                 processed_img = self.preprocess_image(img)
#                 text += pytesseract.image_to_string(processed_img)
#             return text
#         else:
#             img = Image.open(file_path)
#             processed_img = self.preprocess_image(img)
#             return pytesseract.image_to_string(processed_img)

#     def parse_ocr_output(self, text):
#         """Extract structured data from OCR text."""
#         data = {
#             "patient_details": self._extract_patient_info(text),
#             "treatment_details": self._extract_treatment_info(text),
#             "difficulty_ratings": self._extract_difficulty_ratings(text),
#             "patient_changes": self._extract_patient_changes(text),
#             "pain_symptoms": self._extract_pain_symptoms(text),
#             "medical_assistant_data": self._extract_ma_data(text)
#         }
#         return data

#     def _extract_patient_info(self, text):
#         return {
#             "patient_name": self._find_value(r"Patient Name : (.*)", text),
#             "dob": self._find_value(r"DOB : (.*)", text)
#         }

#     def _extract_treatment_info(self, text):
#         return {
#             "date": self._find_value(r"Date : (.*)", text),
#             "injection": self._find_checkbox(r"INJECTION : (YES|NO)", text),
#             "exercise_therapy": self._find_checkbox(r"Exercise Therapy : (YES|NO)", text)
#         }

#     def _extract_difficulty_ratings(self, text):
#         ratings = {}
#         for task in self.difficulty_tasks:
#             pattern = rf"{task.replace('_', ' ').title()}:\s*([0-5])"
#             ratings[task] = self._find_numeric_value(pattern, text)
#         return ratings

#     def _extract_patient_changes(self, text):
#         return {
#             "since_last_treatment": self._find_value(r"Patient changes since last treatment:(.*?)(?=\n\S)", text, True),
#             "since_start_of_treatment": self._find_value(r"Patient changes since the start of treatment:(.*?)(?=\n\S)", text, True),
#             "last_3_days": self._find_value(r"Describe any functional changes within the last three days \(good or bad\):(.*)", text)
#         }

#     def _extract_pain_symptoms(self, text):
#         symptoms = {}
#         for symptom in self.pain_symptoms:
#             pattern = rf"{symptom.title()}:\s*([0-9]{{1,2}})"
#             symptoms[symptom] = self._find_numeric_value(pattern, text)
#         return symptoms

#     def _extract_ma_data(self, text):
#         return {
#             "blood_pressure": self._find_value(r"Blood Pressure: (.*)", text),
#             "hr": self._find_numeric_value(r"HR: (\d+)", text),
#             "weight": self._find_numeric_value(r"Weight: (\d+)", text),
#             "height": self._find_value(r"Height: (.*)", text),
#             "spo2": self._find_numeric_value(r"SpO2: (\d+)", text),
#             "temperature": self._find_value(r"Temperature: (.*)", text),
#             "blood_glucose": self._find_numeric_value(r"Blood Glucose: (\d+)", text),
#             "respirations": self._find_numeric_value(r"Respirations: (\d+)", text)
#         }

#     # Helper methods
#     def _find_value(self, pattern, text, dotall=False):
#         flags = re.DOTALL if dotall else 0
#         match = re.search(pattern, text, flags)
#         return match.group(1).strip() if match else None

#     def _find_numeric_value(self, pattern, text):
#         match = re.search(pattern, text)
#         return int(match.group(1)) if match else None

#     def _find_checkbox(self, pattern, text):
#         match = re.search(pattern, text)
#         return match.group(1) if match else None

# class DatabaseManager:
#     def __init__(self, db_path='patients.db'):
#         self.conn = sqlite3.connect(db_path)
#         self._create_tables()

#     def _create_tables(self):
#         self.conn.execute('''
#             CREATE TABLE IF NOT EXISTS patients (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 name TEXT,
#                 dob TEXT
#             )
#         ''')
#         self.conn.execute('''
#             CREATE TABLE IF NOT EXISTS forms_data (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 patient_id INTEGER,
#                 form_json TEXT,
#                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 FOREIGN KEY(patient_id) REFERENCES patients(id)
#             )
#         ''')
#         self.conn.commit()

#     def insert_data(self, data):
#         cur = self.conn.cursor()
#         cur.execute('''
#             INSERT INTO patients (name, dob)
#             VALUES (?, ?)
#         ''', (data['patient_details']['patient_name'], data['patient_details']['dob']))
        
#         patient_id = cur.lastrowid
        
#         cur.execute('''
#             INSERT INTO forms_data (patient_id, form_json)
#             VALUES (?, ?)
#         ''', (patient_id, json.dumps(data)))
        
#         self.conn.commit()
#         return patient_id

# def process_file(input_path, output_json='output.json'):
#     processor = FormProcessor()
#     db = DatabaseManager()
    
#     text = processor.extract_text(input_path)
#     data = processor.parse_ocr_output(text)
    
#     with open(output_json, 'w') as f:
#         json.dump(data, f, indent=2)
    
#     db.insert_data(data)
#     print(f"Data processed and saved to {output_json} and database")

# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(description='Process patient assessment forms')
#     parser.add_argument('input_file', help='Path to PDF/JPEG file')
#     parser.add_argument('--output', default='output.json', help='Output JSON path')
#     args = parser.parse_args()
    
#     process_file(args.input_file, args.output)