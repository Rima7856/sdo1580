# SDO Client

### 1. clone
```bash
git clone https://github.com/Rima7856/sdo1580.git
cd sdo1580
```

### 2. add .env (change .env.example)

### 3. activate venv

```bash
python -m venv .venv
.\.venv\Scripts\activate # Windows
source .venv/bin/activate # Linux/ MacOS
```

### 4. install requirements
```bash
pip install -r requirements.txt
```

### 5. launch
```bash
python script.py
```

## how it works

1. the script loads a saved session (if any)
2. if the session is expired, it logs in again
3. takes code from `solution.py`
4. sends to the server and displays the results
