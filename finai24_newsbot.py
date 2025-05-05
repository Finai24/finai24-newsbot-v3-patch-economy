import openai
import feedparser
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRAPI_API_TOKEN = os.getenv("STRAPI_API_TOKEN")
MODELLO_OPENAI = os.getenv("MODELLO_OPENAI", "gpt-3.5-turbo")
STRAPI_API_URL = "https://finai24-cms.onrender.com/api/articoli"
ARCHIVIO_FILE = "pubblicati.json"
FEED_LIST = "feeds.txt"
LOG_FILE = "errori_log.txt"

openai.api_key = OPENAI_API_KEY

def log_errore(messaggio):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {messaggio}\n")

def carica_storico():
    if os.path.exists(ARCHIVIO_FILE):
        with open(ARCHIVIO_FILE, "r") as f:
            return json.load(f)
    return []

def salva_storico(storia):
    with open(ARCHIVIO_FILE, "w") as f:
        json.dump(storia, f, indent=2)

def pulizia_storico(storia, giorni=60):
    cutoff = datetime.now(timezone.utc) - timedelta(days=giorni)
    return [s for s in storia if datetime.fromisoformat(s["timestamp"]) > cutoff]

def estrai_feed(feed_url):
    feed = feedparser.parse(feed_url)
    return feed.entries

def gpt_chat(prompt, ruolo):
    try:
        return openai.ChatCompletion.create(
            model=MODELLO_OPENAI,
            messages=[{"role": "system", "content": ruolo}, {"role": "user", "content": prompt}],
            temperature=0.5
        ).choices[0].message.content.strip()
    except Exception as e:
        log_errore(f"Errore GPT: {e}")
        raise

def classifica_categoria(titolo, descrizione):
    prompt = f"""
Titolo: {titolo}
Descrizione: {descrizione}
Assegna una sola categoria tra: macro, mercati, geopolitica, criptovalute, tecnologia, bancario-finanziario, energia, commodities, startup, altro.
Rispondi solo con il nome, senza spiegazioni.
"""
    return gpt_chat(prompt, "Sei un assistente editoriale che classifica articoli di finanza.")

def genera_articolo(titolo, descrizione, link):
    prompt = f"""
Scrivi un articolo originale (~300 parole), basato su:
Titolo: {titolo}
Descrizione: {descrizione}
Fonte: {link}
Stile: giornalistico, paragrafo, link finale alla fonte, nota 'generato da AI'.
"""
    return gpt_chat(prompt, "Sei un giornalista finanziario AI.")

def pubblica_articolo(titolo, contenuto, fonte_url, categoria):
    headers = {
        "Authorization": f"Bearer {STRAPI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "data": {
            "titolo": titolo,
            "contenuto": contenuto,
            "fonte": fonte_url,
            "categoria": categoria,
            "autore": "FinAI24 Newsbot",
            "publishedAt": datetime.now(timezone.utc).isoformat()
        }
    }
    response = requests.post(STRAPI_API_URL, headers=headers, json=payload)
    return response.status_code, response.text

def main():
    print(f"🚀 Avvio FinAI24 Newsbot - modello attivo: {MODELLO_OPENAI}")
    storico = pulizia_storico(carica_storico())
    with open(FEED_LIST, "r") as f:
        feed_urls = [line.strip() for line in f if line.strip()]
    print(f"📥 Caricati {len(feed_urls)} feed da feeds.txt")
    nuovi = 0
    max_pubblicazioni = 2

    for url in feed_urls:
        for voce in estrai_feed(url):
            if nuovi >= max_pubblicazioni:
                break
            titolo = voce.title
            link = voce.link
            if any(link == s["link"] for s in storico):
                continue
            descrizione = voce.get("summary", "")
            try:
                categoria = classifica_categoria(titolo, descrizione)
                articolo = genera_articolo(titolo, descrizione, link)
                status, resp = pubblica_articolo(titolo, articolo, link, categoria)
                print(f"✅ Pubblicato: {titolo} | Categoria: {categoria} | Status: {status}")
                storico.append({"link": link, "timestamp": datetime.now(timezone.utc).isoformat()})
                nuovi += 1
            except Exception as e:
                log_errore(f"Errore con '{titolo}': {e}")
                print(f"❌ Errore con '{titolo}': {e}")
                return

    salva_storico(storico)
    print(f"🔁 Operazione completata. Articoli pubblicati: {nuovi}")

if __name__ == "__main__":
    main()
