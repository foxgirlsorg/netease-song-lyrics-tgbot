
# 🎵 NetEase Song Lyrics Telegram Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight Telegram bot that searches songs on [music.163.com](https://music.163.com) and returns synced LRC lyrics using the NetEase Cloud Music API.

---

## ✨ Features

- 🔍 Search songs by name (artist, title, or mixed queries)
- 📋 Shows up to 6 results with:
  - track name
  - artist(s)
  - duration
- 🎶 Fetch synced LRC lyrics (if available)
- ✂️ Auto-splits long lyrics into multiple messages
- 💬 Works in private chats and groups
- 🚫 Group-safe mode (only `/search <query>` allowed)

--

## ⚙️ Setup

### 1. Create a bot

Use [@BotFather](https://t.me/BotFather) and copy your token.

---

### 2. Configure environment

```bash
cp .env.example .env
````

Edit `.env`:

```env
BOT_TOKEN=your_token_here
```

Or export:

```bash
export BOT_TOKEN=your_token_here
```

---

## 🚀 Running the bot

### 🖥️ Local run

```bash
pip install -r requirements.txt
python bot.py
```

---

### 🐳 Docker run

```bash
docker compose up -d --build
```
---

## 💬 Usage

| Action                   | Description                      |
| ------------------------ | -------------------------------- |
| Send text (private chat) | Searches NetEase instantly       |
| `/search <query>`        | Direct search                    |
| `/search`                | Prompts for input (private only) |
| Tap result               | Fetch lyrics                     |
| Group chats              | Only `/search <query>` works     |

---

## 🌐 How it works

### 🔍 Search API

```
GET https://music.163.com/api/cloudsearch/pc
```

Parameters:

* `s` → query
* `type=1` → songs
* `limit` → results count
* `offset` → pagination

---

### 🎶 Lyrics API

```
GET http://music.163.com/api/song/lyric
```

Parameters:

* `id` → song id
* `lv=-1` → lyrics
* `kv=-1`, `tv=-1` → metadata

Returns:

* `lrc.lyric` → synced LRC format

---
## ⚡ Notes

* NetEase API may rate-limit heavy usage
* Some songs may not include lyrics
* Search quality depends on NetEase ranking (cloudsearch)

---
## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright © 2026 **foxgirls.org** . All rights reserved.