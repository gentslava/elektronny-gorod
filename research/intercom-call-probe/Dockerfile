FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common.py probe_stomp.py probe_sip.py probe_fcm.py probe_sip_media.py probe_push_answer.py ./
# Пробу выбирает command в docker-compose (probe_stomp.py / probe_sip.py / probe_fcm.py)
ENTRYPOINT ["python", "-u"]
CMD ["probe_stomp.py"]
