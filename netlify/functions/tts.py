import json
import asyncio
import base64
import re
import edge_tts

def clean_text(raw_text):
    if not raw_text:
        return ""
    cleaned = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-z]{2,}\b', '', raw_text)
    cleaned = re.sub(r'\+\d+', '', cleaned)
    cleaned = re.sub(r'\s*\.\s*', '. ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

async def synthesize(text, voice, rate="-3%", pitch="-1Hz"):
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("El texto está vacío después de limpiar.")
    comm = edge_tts.Communicate(cleaned, voice, rate=rate, pitch=pitch)
    audio = bytearray()
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
    return bytes(audio)

def handler(event, context=None):
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Content-Type": "application/json"
    }

    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        body = json.loads(event.get("body", "{}"))
        text = body.get("text", "").strip()
        voice = body.get("voice", "es-MX-JorgeNeural")
        rate = body.get("rate", "-3%")
        pitch = body.get("pitch", "-1Hz")

        if not text:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Por favor escribe un texto para generar la voz."})
            }

        audio_bytes = asyncio.run(synthesize(text, voice, rate, pitch))
        b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"audio": b64, "voice": voice, "format": "mp3"})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }
