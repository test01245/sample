This project previously contained extra backend folders that are no longer used:

- backend/ (Node/Express)
- site/backend/ (Node/Express proxy)
- site/src/ (legacy React file)
- site/.env.local (legacy local config)

They can be safely removed. If they still appear in your working copy, delete them manually:

- backend/
- site/backend/
- site/src/
- site/.env.local

Only the following are needed now:

- py_simple/ (Flask backend)
- site/frontend/ (Vite + React UI)
