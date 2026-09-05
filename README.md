# 🛡️ LabelGuard — AI-Powered Packaged Commodity Label Compliance Scanner

[![Vercel Deployment](https://img.shields.io/badge/Vercel-Live%20Demo-black?logo=vercel)](https://labelguard-dusky.vercel.app)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![SIH Problem](https://img.shields.io/badge/SIH-Problem%20SIH26034-orange)](https://www.sih.gov.in/)

> **Automated Legal Metrology & FSSAI Label Auditing System with Real-Time Computer Vision, Client-Side QR Detection, Dual Evidence Storage, and Court-Admissible PDF Generation.**

---

## 📌 Problem Statement (SIH26034)
Under the **Legal Metrology (Packaged Commodities) Rules, 2011** and **FSSAI (Labelling and Display) Regulations, 2020**, manufacturers, packers, and importers in India are legally mandated to declare specific consumer disclosures on packaged goods (e.g., MRP, Net Quantity with standard units, Manufacturing/Packing Date, complete Manufacturer address with PIN code, Consumer Care contact, FSSAI license number, Veg/Non-Veg symbol, and Batch number).

Manual inspection is slow, prone to oversight, and cannot scale across millions of retail stock keeping units (SKUs). **LabelGuard** solves this with an end-to-end edge-assisted automated compliance engine that scans packaged goods in real time, flags non-compliant declarations, cross-validates QR codes, saves audit-trailed evidence, and generates court-admissible PDF inspection reports in seconds.

---

## 🚀 Key Features

- 📹 **Live Camera Scanning with Viewfinder Reticle:**
  - Real-time video viewfinder with active corner reticle (`┌ ┐ └ ┘`).
  - Adaptive resolution to ensure silky-smooth mobile performance and low memory footprint.
  - Multi-camera progressive tier selection (environmental rear camera first, front/webcam fallback).

- ▦ **Client-Side & Server-Side QR Code Validation:**
  - Zero-latency client-side QR decoder (`jsQR`) instantly decodes QR codes offline.
  - Secondary OpenCV QR detector on server cross-verifies QR contents and feeds payload into the Legal Metrology rule engine.

- 🔍 **Multi-Language OCR & Bounding Box Localization:**
  - Tesseract OCR engine supporting dual **English + Hindi (eng+hin)** scripts.
  - OpenCV preprocessing (bilateral denoising, CLAHE contrast enhancement, deskewing).
  - Normalised bounding boxes drawn directly onto the live canvas overlay.

- ⚖️ **Automated Indian Law Rules Engine:**
  - **Rule 6(1)(a):** Complete name & physical address of manufacturer/packer/importer with mandatory 6-digit postal PIN code verification.
  - **Rule 6(1)(c) & Rule 8:** Net Quantity in statutory metric units (g, kg, ml, L) without illegal qualifying words (e.g., "approx", "when packed").
  - **Rule 6(1)(d):** Month & Year of manufacture / pre-packing.
  - **Rule 6(1)(e):** Maximum Retail Price (MRP) format (*"MRP ₹... inclusive of all taxes"*).
  - **Rule 6(1)(f):** Consumer care contact details (phone, email, postal address).
  - **Rule 6(2):** Batch number / Lot code / Code number.
  - **Rule 7 & Second Schedule:** Physical numeral height calculation according to Principal Display Panel (PDP) area in square centimetres.
  - **FSSAI Food Safety Act:** 14-digit FSSAI license/registration number validation.
  - **FSSAI 2020 Regs:** Mandatory Vegetarian (green filled circle) or Non-Vegetarian (brown/red filled circle) declaration.
  - **Expiry / Best Before:** Mandatory shelf-life declarations for food and perishable goods.
  - **Country of Origin:** Mandatory declarations on imported packaged commodities.

- 💾 **Dual Evidence Archiving (`uploads/` & `evidence/`):**
  - Original raw uploaded images automatically saved to `uploads/{id}.jpg` and `backend/uploads/{id}.jpg`.
  - Audited bounding-box evidence saved to `backend/evidence/{id}_annotated.jpg`.
  - SHA-256 cryptographic hashing on every image ensures non-repudiation in court.

- 📄 **Court-Admissible PDF Inspection Reports:**
  - One-click instant vector PDF report generation with ReportLab.
  - Includes inspection timestamp, product metadata, rule-by-rule breakdown with statutory references, measured vs required metrics, annotated evidence photo, and digital verification seal.

- 📊 **Real-Time Enforcement Dashboard:**
  - Live statistics: Total inspections, compliance rate, open violations, average processing latency.
  - Violations-by-rule frequency bars.
  - Recent inspections log with **1-click direct links** to view saved original images and download court PDF certificates.

---

## 🏗️ System Architecture

```
                               ┌────────────────────────┐
                               │   User Device / Phone  │
                               │  (Mobile or Desktop)   │
                               └───────────┬────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
           [HTTPS: Static Hosting]                  [API: OCR & AI Backend]
             Vercel Edge Network                      FastAPI + Python 3.12
       https://labelguard-dusky.vercel.app          (Localhost / Cloudflare)
                        │                                     │
            ├── HTML5 Glassmorphism UI              ├── OpenCV Preprocessing
            ├── Client-side QR (jsQR)               ├── PyTesseract OCR (Eng+Hin)
            └── LocalStorage API Resolver           ├── Rules & Scale Engine
                                                    ├── Dual File Archiving
                                                    │   ├── uploads/{id}.jpg
                                                    │   └── evidence/{id}.jpg
                                                    ├── SQLite / SQLAlchemy DB
                                                    └── ReportLab PDF Generator
```

---

## 💻 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Vanilla HTML5, Modern CSS3 (Dark Glassmorphism, CSS Custom Properties), Vanilla JavaScript (ES6+), [jsQR](https://github.com/cozmo/jsQR) |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) (ASGI), Pydantic |
| **Computer Vision** | [OpenCV (cv2)](https://opencv.org/), [Pillow (PIL)](https://python-pillow.org/) |
| **OCR Engine** | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) via [PyTesseract](https://pypi.org/project/pytesseract/) |
| **Database & ORM** | [SQLite](https://www.sqlite.org/), [SQLAlchemy 2.0](https://www.sqlalchemy.org/) |
| **Document Generation** | [ReportLab](https://www.reportlab.com/) (Court-admissible PDF generator) |
| **Tunneling & Cloud** | [Cloudflare Tunnel (`cloudflared`)](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/), [Vercel](https://vercel.com/) |

---

## 📂 Project Directory Structure

```
labelguard/
├── backend/
│   ├── evidence/            # Audited evidence photos & annotated overlays
│   ├── uploads/             # Raw uploaded images from users
│   ├── db.py                # Database models, queries, and KPI aggregation
│   ├── extractor.py         # Regex & NLP parser for label entities (MRP, PIN, FSSAI)
│   ├── main.py              # FastAPI server, endpoints, static mounts, and router
│   ├── ocr.py               # Image deskewing, preprocessing, Tesseract runner & QR
│   ├── report.py            # PDF generation with ReportLab
│   ├── requirements.txt     # Python backend dependencies
│   ├── rules.py             # Indian Legal Metrology & FSSAI statutory rule engine
│   └── labelguard.db        # SQLite database
├── frontend/
│   └── index.html           # Single-page application (Scanner, Viewer & Dashboard)
├── uploads -> backend/uploads # Convenient root symlink to user uploads
├── vercel.json              # Vercel deployment configuration
├── .gitignore
└── README.md
```

---

## ⚡ Quick Start Guide

### Prerequisites
1. **Python 3.10+** (Python 3.12 recommended)
2. **Tesseract OCR:**
   - **macOS:** `brew install tesseract tesseract-lang`
   - **Ubuntu/Debian:** `sudo apt-get install tesseract-ocr tesseract-ocr-hin`
   - **Windows:** Download installer from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/labelguard.git
cd labelguard
```

### 2. Set Up Python Virtual Environment
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Start the Backend Server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- API Health: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- Swagger API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Frontend: [http://localhost:8000](http://localhost:8000)

### 4. Running the Frontend
- **Option A (All-in-One):** The FastAPI backend automatically serves the frontend at `http://localhost:8000`.
- **Option B (Vercel):** Visit the deployed frontend at:
  👉 **[https://labelguard-dusky.vercel.app](https://labelguard-dusky.vercel.app)**
- **Option C (Phone over Local WiFi / Tunnel):**
  Expose your local backend over HTTPS for mobile phone testing:
  ```bash
  cloudflared tunnel --url http://localhost:8000
  ```
  Copy the generated `https://<random>.trycloudflare.com` URL and set it in the frontend under **⚙ Server**.

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Healthcheck and timestamp |
| `POST` | `/api/scan` | Analyze image (file multipart) with mode (`live` or `upload`) |
| `GET` | `/api/inspections` | List latest inspection records |
| `GET` | `/api/inspections/{iid}` | Get inspection details by unique ID |
| `GET` | `/api/inspections/{iid}/image` | Retrieve original raw uploaded image |
| `GET` | `/api/inspections/{iid}/annotated` | Retrieve bounding-box annotated evidence image |
| `GET` | `/api/report/{iid}.pdf` | Stream court-admissible audit PDF report |
| `GET` | `/api/stats` | Aggregate dashboard metrics, compliance rates & rule violations |
| `GET` | `/evidence/{filename}` | Statically served evidence image |
| `GET` | `/uploads/{filename}` | Statically served raw upload image |

---

## 👥 Team Tech Titans (SIH 2024 / 2026)
Developed for **Smart India Hackathon** — Problem Statement **SIH26034**.

© 2026 Team Tech Titans · LabelGuard
