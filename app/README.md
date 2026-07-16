# YC Founder Email Review

From the project root, install Streamlit and run:

```powershell
python -m pip install -r app/requirements.txt
python -m streamlit run app/app.py
```

The app reads `outputs/yc-founders.json`, stores progress in `app/progress.db`, and exports all founders as `yc-founders-with-emails.csv` from the sidebar.

For deployment, upload the repository to Streamlit Community Cloud and set the app file to `app/app.py`. For two people to share the same progress, use a shared database or hosted storage; a local SQLite file is shared only by processes using the same deployed app instance and filesystem.
