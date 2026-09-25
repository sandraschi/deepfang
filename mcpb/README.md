# deepfang (MCPB Bundle)

Docker-Compose execution isolation stack: Sanitizer + DeepSeek adjudicator + air-gapped worker on Goliath

## Usage

Add to \claude_desktop_config.json\:
\\\json
{
  "mcpServers": {
    "deepfang": {
      "command": "uv",
      "args": ["run", "--directory", "\D:\Dev\repos", "python", "-m", "deepfang"],
      "env": { "PYTHONPATH": "\D:\Dev\repos/src" }
    }
  }
}
\\\

## Tools

- **deepfang_status**: deepfang_status

## Requirements

- Python 3.12+
- uv
