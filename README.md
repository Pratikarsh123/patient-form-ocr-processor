 Overview

The Patient Form OCR Processor is a Python-based solution designed to:

Extract text from scanned patient assessment forms (JPEG/PDF) using OCR.

Parse and structure the extracted data into JSON format.

Store the structured data in an SQL database.

Provide an easy-to-use script for automation.

🚀 Features

📄 Extract text from PDF & Image files using Tesseract OCR.

🖼️ Convert PDFs to images using pdf2image.

📦 Store extracted data in SQLite database.

📊 JSON structured output.

🔄 Automate processing using command-line arguments.

🛠 Installation

1️⃣ Clone the Repository

git clone https://github.com/your-username/patient-form-ocr-processor.git
cd patient-form-ocr-processor

2️⃣ Install Dependencies

pip install -r requirements.txt

3️⃣ Install External Dependencies

Install Tesseract OCR and add it to the system PATH.

Install Poppler for Windows and add its bin folder to the system PATH.

🔍 Usage

Extract Data from a PDF or Image

python main.py samples/sample.pdf

View Processed JSON Output

cat result.json

View Data in Database
