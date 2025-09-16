name: build
on:
  workflow_dispatch:
  schedule:
    - cron: "0 */5 * * *"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - name: Install ffmpeg
        run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install --prefer-binary -r requirements.txt
      - name: Write secrets to files
        env:
          CONFIG_JSON: ${{ secrets.CONFIG_JSON }}
          TOKEN_JSON: ${{ secrets.TOKEN_JSON }}
          CLIENT_SECRET_JSON: ${{ secrets.CLIENT_SECRET_JSON }}
        run: |
          echo "$CONFIG_JSON" > config.json
          echo "$TOKEN_JSON" > token.json
          echo "$CLIENT_SECRET_JSON" > client_secret.json
      - name: Run main script
        run: |
          echo "🚀 Starting script..."
          python main.py
