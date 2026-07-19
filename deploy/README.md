DigitalOcean one-shot setup

1. Create an Ubuntu 24.04 droplet.
2. SSH in as root and run:

   curl -fsSL https://raw.githubusercontent.com/sireenmalik/carrier-voice-agent/main/deploy/setup-droplet.sh | bash

3. After setup completes, open http://<droplet-ip>/ in a browser to verify the frontend loads.

4. Fill /etc/carrier-voice-agent.env with your Bedrock settings, for example:

   BEDROCK_MODEL_ID_TEXT=your-bedrock-text-model-id
   AWS_REGION=us-east-1

5. To enable GitHub Actions-based CD, add these repository secrets in Settings > Secrets:
   - DROPLET_HOST (ip or hostname)
   - DROPLET_USER (user to SSH as; must be able to sudo to run deploy command)
   - DROPLET_SSH_KEY (private key content for SSH authentication)

Notes:
- The setup script installs nginx and configures a site. The nginx config turns off proxy_buffering for the /turn and /api/ endpoints which is necessary for Server-Sent Events (SSE) to stream correctly.
- The deploy scripts do NOT attempt to open ports other than 80 (nginx). If you expose SSH on a different port, adjust UFW commands accordingly.
- This automation does not add any secrets to the droplet; set BEDROCK_MODEL_ID_TEXT and AWS_REGION in /etc/carrier-voice-agent.env after setup.
