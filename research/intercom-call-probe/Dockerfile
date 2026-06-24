FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common.py probe_stomp.py probe_sip.py probe_fcm.py probe_sip_media.py probe_push_answer.py ./
COPY probe_mic_uplink.py mic_ws_probe.html ./
# Пробу выбирает command в docker-compose (probe_stomp.py / probe_sip.py / probe_fcm.py / probe_mic_uplink.py)
ENTRYPOINT ["python", "-u"]
CMD ["probe_stomp.py"]
