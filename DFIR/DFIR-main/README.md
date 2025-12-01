# DFIR Report Generation System

A web-based system for Digital Forensics and Incident Response (DFIR) analysis and professional HTML report generation from Wazuh logs.

## Overview

This system provides a web interface where you can:
- Upload Wazuh log files (JSON format)
- Run DFIR analysis with AI agents
- Generate professional HTML reports

The system uses two specialized AI agents:
1. **DFIR Agent**: Analyzes security logs and extracts forensic data
2. **Reporting Agent**: Generates structured HTML reports from the analysis

## Quick Start

### 1. Start the System

```bash
docker-compose up -d
```

### 2. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:5000
```

### 3. Use the System

1. **Upload a Wazuh log file** (JSON format) using the file upload area
2. **Click "Run DFIR Analysis"** to analyze the log file
3. **Click "Generate HTML Report"** to create the final report
4. **View the generated report** in the reports section

## Model Configuration

The system supports multiple LLM providers (cloud and local). Configure your preferred model in the `.env` file:

### Cloud Models

#### Using Alias (Recommended)
```bash
CAI_MODEL="alias1"
ALIAS_API_KEY="your-alias-api-key"
```

#### Using OpenAI
```bash
CAI_MODEL="gpt-4o"
OPENAI_API_KEY="your-openai-api-key"
```

#### Using Anthropic Claude
```bash
CAI_MODEL="claude-3-opus"
ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### Local Models (Ollama)

To use local models with Ollama:

1. **Uncomment Ollama service** in `docker-compose.yml`:
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama-server
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    # ... rest of config
```

2. **Uncomment dependencies** in `cai-framework` service:
```yaml
depends_on:
  ollama:
    condition: service_healthy
networks:
  - dfir_network
```

3. **Configure in `.env`**:
```bash
CAI_MODEL="ollama"
OLLAMA_API_BASE="http://ollama:11434/v1"
OLLAMA_MODEL="llama3.2:1b"  # or llama3.2:3b, llama3, etc.
OLLAMA_API_KEY="ollama"
```

4. **Pull the model**:
```bash
docker exec ollama-server ollama pull llama3.2:1b
```

5. **Restart containers**:
```bash
docker-compose restart
```

## Environment Variables

1. **Copy the example file:**
```bash
cp .env.example .env
```

2. **Edit `.env` and configure your API keys:**

The `.env.example` file contains all available configuration options for:
- **Cloud models**: Alias, OpenAI, Anthropic
- **Local models**: Ollama configuration
- **Optional features**: Perplexity, Shodan, Google Search
- **Timeouts and advanced settings**

**Minimum required configuration:**

For **Alias** (recommended):
```bash
CAI_MODEL="alias1"
ALIAS_API_KEY="your-alias-api-key"
```

For **OpenAI**:
```bash
CAI_MODEL="gpt-4o"
OPENAI_API_KEY="your-openai-api-key"
```

For **Ollama** (local):
```bash
CAI_MODEL="ollama"
OLLAMA_API_BASE="http://ollama:11434/v1"
OLLAMA_MODEL="llama3.2:1b"
OLLAMA_API_KEY="ollama"
```

See `.env.example` for complete configuration options.

## Project Structure

```
dfir_report/
├── main.py                    # Main orchestrator
├── docker-compose.yml         # Docker configuration
├── Dockerfile                 # Container image definition
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables
├── frontend/
│   ├── app.py                # Flask web application
│   └── templates/
│       └── index.html        # Web interface
├── agents/
│   ├── dfir_agent.py         # DFIR analysis agent
│   └── reporting_agent.py    # Report generation agent
├── html_template/
│   └── html_report_template.html  # HTML report template
├── test_data/                # Sample Wazuh logs
│   ├── wazuh_easy_case.json
│   ├── wazuh_medium_case.json
│   └── wazuh_hard_case.json
├── dfir_reports/             # Generated reports
└── logs/                     # CAI framework logs
```

## Supported File Formats

- **JSON**: Wazuh alert logs in JSON format
- **TXT**: Plain text log files
- **LOG**: Standard log files
- **CSV**: Comma-separated values
- **XML**: XML formatted logs

Maximum file size: 50MB

## Report Features

The generated HTML reports include:
- Executive summary
- Attack timeline visualization
- Statistics cards (IOCs, compromised systems, duration)
- Entry points analysis
- Attack objectives
- Indicators of Compromise (IOCs)
- Security recommendations
- MITRE ATT&CK technique mapping

## Troubleshooting

### Container won't start
```bash
docker-compose down
docker-compose up -d --build
```

### Model not responding
- Check API keys in `.env` file
- Verify `CAI_MODEL` matches your API key type
- For Ollama: ensure model is downloaded (`docker exec ollama-server ollama list`)

### Frontend not accessible
- Check container is running: `docker ps`
- Verify port 5000 is not in use
- Check logs: `docker logs cai-dfir-container`

## License

This project is part of the CAI Framework ecosystem.
