const { MsEdgeTTS, OUTPUT_FORMAT } = require('msedge-tts');

function cleanText(rawText) {
  if (!rawText) return "";
  return rawText
    .replace(/https?:\/\/\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-z]{2,}\b/g, '')
    .replace(/\+\d+/g, '')
    .replace(/\s*\.\s*/g, '. ')
    .replace(/\s+/g, ' ')
    .trim();
}

exports.handler = async (event) => {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Content-Type': 'application/json'
  };

  if (event.httpMethod === 'OPTIONS') {
    return {
      statusCode: 200,
      headers,
      body: ''
    };
  }

  try {
    const body = JSON.parse(event.body || '{}');
    const rawText = body.text || '';
    const voice = body.voice || 'es-MX-JorgeNeural';
    const rate = body.rate || '-3%';
    const pitch = body.pitch || '-1Hz';

    const text = cleanText(rawText);
    if (!text) {
      return {
        statusCode: 400,
        headers,
        body: JSON.stringify({ error: 'Por favor escribe un texto para generar la voz.' })
      };
    }

    const tts = new MsEdgeTTS();
    await tts.setMetadata(voice, OUTPUT_FORMAT.AUDIO_24KHZ_96KBITRATE_MONO_MP3);
    
    const audioData = await new Promise((resolve, reject) => {
      const { audioStream } = tts.toStream(text, { rate, pitch });
      const chunks = [];
      audioStream.on('data', (chunk) => chunks.push(chunk));
      audioStream.on('end', () => resolve(Buffer.concat(chunks)));
      audioStream.on('error', (err) => reject(err));
    });

    const b64 = audioData.toString('base64');

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        audio: b64,
        voice,
        format: 'mp3'
      })
    };
  } catch (error) {
    console.error('TTS handler error:', error);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: error.message || 'Error al generar la voz en el servidor.' })
    };
  }
};
