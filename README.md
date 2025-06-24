# 📚 Campus Hub: Lost & Found + Marketplace

A Flask-based web application designed for college campuses to manage lost & found items and facilitate peer-to-peer marketplace listings (buy/sell/trade). Features include secure registration with email verification, user profile dashboards, and item management.

---

## 🚀 Features

- 🔒 **User Authentication** with email verification  
- 📦 **Lost & Found** item submission and tracking  
- 🛍️ **Marketplace** for buying/selling items  
- 🧑‍💻 **Profile Management**: view, edit, and delete your listings  
- ✉️ **Email alerts** using Gmail SMTP  
- 🖼️ **Image uploads** with compression  
- 🔐 **Rate-limited registration**  
- 🎨 **Clean, responsive UI** (Jinja2 + Tailwind-ready)  

---

## 🛠️ Tech Stack

| Tech         | Usage                        |
|--------------|------------------------------|
| Python 3.10+ | Backend logic                |
| Flask        | Web framework                |
| SQLite       | Database                     |
| Flask-Mail   | Email verification           |
| Flask-Login  | Authentication & sessions    |
| Jinja2       | HTML templating              |
| HTML/CSS     | Frontend                     |

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/campus-lost-found-market.git
cd campus-lost-found-market
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file in the root directory

```env
FLASK_SECRET_KEY=your-secret-key
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

> ⚠️ Make sure you’ve enabled [App Passwords](https://myaccount.google.com/apppasswords) in your Google account.

### 5. Run the application

```bash
python main.py
```

Visit: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🧪 Testing Accounts

- Use `Continue without login` to explore as a guest.
- Admin access and additional roles can be set manually in the database.

---

## 🔒 Security 

- Secrets are managed through `.env` — **never commit secrets**.
- `config.py` should remain in `.gitignore`.

