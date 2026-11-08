# CircuitStock Inventory Tracker

A beginner-friendly web app for tracking electronic components, stock movements, workshop equipment, and maintenance history. It uses Flask, SQLite, HTML, CSS, and plain JavaScript-free forms.

## Run it

1. Install Python 3.10 or newer.
2. In this folder, create and activate a virtual environment:

   **Windows PowerShell**
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install the one dependency and start the app:
   ```powershell
   pip install -r requirements.txt
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.

The first start creates `inventory.db` and adds a few sample components and equipment records. Delete that file if you want a completely blank database.

## Accounts and shared use

When you open the app after this update, create an account from the **Create an account** link, then sign in. Every registered team member has their own username and password, while inventory and maintenance records are shared across the workshop.

The **Delete** button beside a component asks for confirmation and removes that component along with its stock-movement history. This action cannot be undone.

## How the app is organised

- `app.py` contains the Flask routes and SQLite database setup.
- `templates/` contains the HTML screens. `base.html` is the shared navigation and page structure.
- `static/style.css` contains the responsive visual design.
- `inventory.db` is created automatically and stores all records locally.

## What each feature does

- **Components:** add part numbers, names, categories, stock quantity, storage location, suppliers, and minimum-stock levels. Search and filter the list.
- **Accounts:** create separate sign-ins for team members; users must sign in before accessing workshop data.
- **Stock in/out:** choose a component and record incoming or used quantity. The current total updates automatically and every movement is kept for the dashboard.
- **Equipment:** register workshop assets, their service interval, status, and next service date.
- **Maintenance history:** record work completed, technician, date, and optional cost. Saving a service automatically schedules the next one using the asset's interval.
- **Dashboard:** highlights low-stock components and equipment due within 14 days; dates before today appear as overdue.

## Beginner walkthrough

1. Flask reads `@app.route(...)` functions in `app.py` to decide which page to display.
2. `init_db()` runs when the program starts and creates four simple tables: components, transactions, assets, and service history.
3. Forms send data back to Flask using `POST`. The corresponding route validates it, updates SQLite, and returns to the relevant page.
4. Dashboard numbers come from short SQL queries such as `SUM(quantity)` and `COUNT(*)`.
5. Jinja syntax in the templates, for example `{% for item in components %}`, turns Python data into HTML.

## Next useful improvements

- Add edit and delete actions with confirmation screens.
- Add user accounts before sharing the app with a team.
- Export component data to CSV and add barcode/QR scanning.
- Move the secret key to an environment variable and turn off Flask debug mode for deployment.
