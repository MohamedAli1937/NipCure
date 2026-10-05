<p align="center">
  <img src="frontend/assets/logo.svg" width="90" alt="NipCure Logo">
</p>

<h2 align="center">NipCure</h2>

<p align="center">
  An AI-powered healthcare assistant designed to help older adults understand and manage information from their medical reports.
</p>

---

## What is NipCure?

NipCure is a healthcare assistant designed with **older adults** in mind. It transforms complex medical PDF reports into clear, structured **Care Plans** containing medications, instructions, warnings, follow-ups, and questions for the doctor.

Patients can also add their **age, allergies, dietary restrictions, and preferences**. NipCure compares this profile with the report to detect potential conflicts and mark them as **"Needs verification."**

The goal is simple: make medical information **easier to understand, organize, and remember** — not replace healthcare professionals.

---

## How It Works

The core workflow is intentionally simple:

```mermaid
flowchart LR
    A[Medical Report PDF] --> B[Extract Text]
    B --> C[Gemma 3]
    C --> D[Medical Care Plan]
    D --> E[Patient Profile]
    E --> F[Conflict Detection]
    F --> G[Safe Personalization]
    G --> H[Final Care Plan]
```

The medical report is always processed **before** the patient's profile.

This means the patient's preferences do not change or override information extracted from the medical document.

---

## Care Plan

The generated Care Plan organizes the information into simple sections:

```text
Care Plan
├── Important Warnings
├── Medications Mentioned in the Report
├── What To Do
├── Food Guidance
├── Follow-Up
├── Questions For Your Doctor
└── Evidence & Sources
```

This structure is designed to make the result easier to scan and understand, particularly for older users who may not want to read through a long medical document.

---

## Patient Profile

Each patient can maintain a personal profile containing:

```text
Patient Profile
├── Age
├── Allergies
├── Food Preferences
├── Foods to Avoid
├── Dietary Restrictions
└── Additional Notes
```

The profile is used for **comparison and personalization**, not as a replacement for the medical report.

```mermaid
flowchart LR
    A[Medical Report] --> B[Report-Based Care Plan]
    B --> C[Compare With Profile]
    C --> D{Conflict?}
    D -->|No| E[Safe Personalization]
    D -->|Yes| F[Needs Verification]
    F --> G[Final Care Plan]
    E --> G
```

---

## Accessibility

NipCure was designed with older adults in mind.

The interface focuses on:

- Large and readable text
- Clear sections
- Simple navigation
- High-contrast elements
- Large buttons
- Minimal unnecessary interaction
- Voice access to the Care Plan
- Clear warnings and important information
- Avoiding complex medical terminology where possible

The objective is to make the application usable even for someone who is not comfortable with complex digital interfaces.

---

## Voice Assistance

NipCure can integrate **ElevenLabs** to convert the final Care Plan into natural voice narration.

```mermaid
flowchart LR
    A[Final Care Plan] --> B[ElevenLabs]
    B --> C[Voice Narration]
    C --> D[Patient]
```

This provides an alternative to reading the entire Care Plan and can be particularly useful for older adults.

If ElevenLabs is unavailable, NipCure can fall back to the browser/device speech synthesis.

---

## Educational Resources

NipCure also provides a **Learn More** section using **SerpApi**.

The system searches for educational resources related to topics explicitly identified in the medical report.

```mermaid
flowchart LR
    A[Medical Report Topics] --> B[SerpApi]
    B --> C[Medical Resources]
    C --> D[Learn More]
```

The research component is intentionally separated from Care Plan generation.

Search results are **educational only** and are not used to generate, modify, or override medical instructions.

The system prioritizes resources from recognized medical institutions and organizations such as:

- Mayo Clinic
- MedlinePlus / NIH
- CDC
- Cleveland Clinic
- NHS
- Harvard Health Publishing

---

## Technical Architecture

NipCure is designed as a **local-first AI application**.

The core AI pipeline runs locally using **Gemma 3 through Ollama**. This means medical documents can be processed without sending their contents to a third-party LLM API.

```mermaid
flowchart LR
    U[Patient] --> FE[Frontend<br/>HTML / CSS / JavaScript]
    FE --> API[FastAPI Backend]

    API --> DB[(PostgreSQL)]
    API --> PDF[PyPDF]
    PDF --> AI[Ollama]
    AI --> GEMMA[Gemma 3]

    GEMMA --> PLAN[Care Plan]
    PLAN --> TTS[ElevenLabs]
    PLAN --> SEARCH[SerpApi]

    API --> PROFILE[Patient Profile]
    PROFILE --> AI
```

### Why Local AI?

Running Gemma 3 locally provides several advantages:

- Medical documents can remain on the user's machine
- No proprietary LLM API is required for the core AI pipeline
- No per-request LLM cost
- The model can be replaced or modified more easily
- The application can continue working without an internet connection for the core AI processing
- Open-weight AI becomes the core of the application rather than an optional feature

---

## Project Structure

```text
NipCure/
│
├── backend/
│   ├── app/
│   │   ├── ai/
│   │   │   ├── gemma.py
│   │   │   ├── prompts.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── auth.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schema.py
│   │   └── main.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── assets/
│   │   └── logo.svg
│   │
│   ├── css/
│   │   └── style.css
│   │
│   ├── js/
│   │   ├── api.js
│   │   ├── config.js
│   │   ├── dashboard.js
│   │   ├── login.js
│   │   ├── profile.js
│   │   └── register.js
│   │
│   ├── dashboard.html
│   ├── index.html
│   ├── login.html
│   └── profile.html
│
├── .gitignore
└── README.md
```

---

## Tools & Technologies

| Area | Technology | Purpose |
|---|---|---|
| AI Model | **Gemma 3** | Understand medical reports and generate Care Plans |
| Local AI Runtime | **Ollama** | Run Gemma 3 locally |
| Backend | **Python / FastAPI** | API and application logic |
| ORM | **SQLAlchemy** | Database interaction |
| Frontend | **HTML / CSS / JavaScript** | Patient interface |
| Database | **PostgreSQL** | Users, profiles, and reports |
| PDF | **PyPDF** | Extract text from medical PDFs |
| Voice | **ElevenLabs** | Care Plan voice narration |
| Research | **SerpApi** | Educational medical resource discovery |
| Authentication | **JWT / bcrypt** | Authentication and password security |

---

## Main Integrations

### Gemma 3

**Gemma 3** is at the core of NipCure.

It processes the extracted medical report and produces a structured Care Plan based on information contained in the document.

The model runs locally rather than through a proprietary cloud LLM API.

### Ollama

**Ollama** provides the local runtime used to run Gemma 3.

The local pipeline is:

```text
Medical PDF
    ↓
PyPDF
    ↓
Extracted Text
    ↓
FastAPI
    ↓
Ollama
    ↓
Gemma 3
    ↓
Structured Care Plan
```

### ElevenLabs

Used for natural voice narration of the final Care Plan.

ElevenLabs is an optional external service and is not part of the core medical reasoning pipeline.

### SerpApi

Used to discover additional educational resources related to medical topics found in the report.

SerpApi results are kept separate from the AI-generated Care Plan.

### PostgreSQL

Stores:

- User accounts
- Patient profiles
- Uploaded report information
- Generated Care Plans

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/MohamedAli1937/NipCure.git
cd NipCure
```

### 2. Install Ollama

Install Ollama and download Gemma 3:

```bash
ollama pull gemma3:4b
```

Verify that the model is available:

```bash
ollama list
```

You can also test it directly:

```bash
ollama run gemma3:4b
```

### 3. Start PostgreSQL

NipCure uses PostgreSQL for users, profiles, and reports.

For local development, PostgreSQL can be run with Docker:

```bash
docker run --name nipcure-postgres \
  -e POSTGRES_DB=nipcure \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5433:5432 \
  -d postgres:17
```

### 4. Configure environment variables

Create:

```text
backend/.env
```

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5433/nipcure

JWT_SECRET_KEY=your-long-random-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

SERPAPI_API_KEY=
```

The ElevenLabs and SerpApi keys are optional.

Gemma does **not** require a Hugging Face token because the model runs locally through Ollama.

### 5. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 6. Start the backend

From the project root:

```bash
uvicorn app.main:app --reload --app-dir backend
```

The API will be available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

### 7. Open the frontend

Open:

```text
frontend/index.html
```

or serve the frontend with a local static server.

---

## API

The backend exposes REST endpoints for the main application features:

```text
Authentication
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

Profile
GET    /api/profile
PUT    /api/profile

Reports
GET    /api/reports
POST   /api/reports
GET    /api/reports/{id}
DELETE /api/reports/{id}
POST   /api/reports/{id}/reexamine
POST   /api/reports/{id}/voice
GET    /api/reports/{id}/research
```

---

## Safety Approach

NipCure follows a **report-first** approach:

```mermaid
flowchart LR
    A[Medical Report] --> B[Extracted Facts]
    B --> C[Care Plan]
    C --> D[Patient Profile]
    D --> E[Conflict Detection]
    E --> F[Safe Personalization]
```

The system is designed to avoid:

- Inventing medications or dosages
- Inventing medical instructions
- Inventing diagnoses or warnings
- Silently overriding information from the report
- Using web search results as medical instructions
- Presenting the system as a replacement for a doctor

When information is unclear or conflicting, the system can mark it as **"Needs verification."**

The medical report is the primary source. Patient profile information is secondary and is used for comparison and personalization.

For development and testing, NipCure should use **synthetic or de-identified medical documents** rather than real patient data.

---

## Privacy

NipCure's local AI architecture is designed to keep the core medical-document processing on the user's machine.

```text
Medical Report
      ↓
Local FastAPI
      ↓
Local Ollama
      ↓
Local Gemma 3
      ↓
Care Plan
```

The core AI processing does not require sending the medical report to a proprietary cloud LLM.

Optional external services such as ElevenLabs and SerpApi are separate from the core Gemma pipeline.

---

## Hacktoberfest

Built for the **Hacktoberfest Weekend Challenge: Build for a Friend**.

NipCure uses **Gemma 3**, an open-weight model, as the core AI component and runs inference locally through **Ollama**.

The local-first approach is particularly relevant for healthcare because it allows the application to process sensitive medical documents without requiring a proprietary cloud LLM API.

---

## License

MIT License.

---

## Why "NipCure"?

**NipCure** = **Nippur + Cure**.

Nippur gave us one of the oldest known medical texts. We just gave it a **21st-century AI upgrade**.