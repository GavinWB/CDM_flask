# Setup
## Activate virtual environment and install neccessary packages
```
virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```
## Recreate DB
```
rm db.sqlite
python
>>> from app import *
>>> db.create_all()
>>> exit()
```
## Run the server
```
python app.py
```
