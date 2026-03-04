# Exam Test Webapp

**Version 1.0**

**Created by**: Ye Htut Win

**License**: Open Source (Non-Free) - Usage requires licensing agreement. See LICENSE file for details.

This is a Flask web application for administering school exams locally. Students can access the test via a local IP network without requiring an online account.

## Features
- Question types: single choice, multiple choice, gap fill, short text, long text
- Role-based access: admin, teacher, student
  - **Admin** can create teacher or student accounts
  - **Teacher** can create exams and questions
  - **Student** logs in to take exams; grades are stored
- Data persisted in SQLite (`exam.db`)
- Authentication handled by Flask-Login
- Dockerized for easy distribution via Docker Hub

## Running locally

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
   > **Note**: This project targets Flask 3; earlier versions may still support `@app.before_first_request`. In Flask 3 the database initialization runs manually in the `__main__` section inside an application context.
2. Run the application:
   ```bash
   python app.py
   ```
3. Open your browser to `http://localhost:5000` or use your local IP.
4. Log in using the default administrator account (created on first run):
   - **username**: `admin`
   - **password**: `admin`
   After logging in as admin you can create teacher and student users via the admin dashboard.

Students should use the credentials provided by the admin to log in and access the exam list.

> **Database schema changes**: If you modify models (e.g. add time limits), delete `exam.db` and restart the app to rebuild the tables. Existing data will be lost.

## User Interface
The application now uses Bootstrap for a clean "quiz"-style appearance similar to RosarioSIS. Questions are displayed in cards, and form elements are styled for better usability.

## Exam Features
- **Time limits** – teachers specify a duration (minutes) when creating or editing an exam. Students see a countdown timer and the exam auto‑submits when time runs out.
- **Score visibility** – students are not shown their score after submission; only teachers and admins can view results.
- **Grade export** – teachers (and admins) can view all student grades for an exam and download them as a CSV sheet, which can later be shared or published. A public URL is also available for each exam (`/public/grades/<id>.csv`).
- **Summary dashboard** – the teacher dashboard now shows per-exam attempt counts and average scores.
- **Per-question statistics** – when editing an exam teachers can see how many students answered each question correctly.
- **Timed-auto-pause** – the countdown timer pauses automatically when the browser tab loses focus and resumes on return.
- **Account management** – admins can delete teacher or student accounts directly from the admin dashboard. When a student account is removed their associated grades are also deleted. Admins can also change their password via the admin dashboard.

## Docker & Docker Hub

The application is containerized and available on Docker Hub for easy deployment.

### Build and Run Locally

```bash
docker build -t exam-test-webapp:1.0 .
docker run -p 5000:5000 -v "$PWD/exam.db:/app/instance/exam.db" exam-test-webapp:1.0
```

### Use from Docker Hub

```bash
docker run -p 5000:5000 -v exam-db:/app/instance yehtutwin/exam-test-webapp:1.0
```

Replace `yehtutwin` with your Docker Hub username when publishing.

### Push to Docker Hub

1. Tag the image:
   ```bash
   docker tag exam-test-webapp:1.0 <yourhubusername>/exam-test-webapp:1.0
   ```

2. Log in to Docker Hub:
   ```bash
   docker login
   ```

3. Push the image:
   ```bash
   docker push <yourhubusername>/exam-test-webapp:1.0
   ```

The application will be available at `http://localhost:5000` with the default admin credentials (username: `admin`, password: `admin`).

## Notes
- Extend this template with question storage and scoring as needed.
