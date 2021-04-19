FROM python:3

COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py .

ENV WALLET=
EXPOSE 11811

CMD python -u main.py --wallet ${WALLET} --port 11811
