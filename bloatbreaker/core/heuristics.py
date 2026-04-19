# bloatbreaker/core/heuristics.py

# Lista de padrões de pacotes UWP (Appx) geralmente inúteis em ambientes de produção
BLOAT_APP_PATTERNS = [
    "Microsoft.ZuneVideo", "Microsoft.ZuneMusic", "Microsoft.WindowsFeedbackHub",
    "Microsoft.GetHelp", "Microsoft.Getstarted", "Microsoft.YourPhone",
    "Microsoft.WindowsMaps", "Microsoft.XboxApp", "Microsoft.Xbox.TCUI",
    "Microsoft.XboxGameOverlay", "Microsoft.XboxGamingOverlay",
    "Microsoft.XboxIdentityProvider", "Microsoft.XboxSpeechToTextOverlay",
    "Microsoft.BingNews", "Microsoft.BingWeather", "Microsoft.SkypeApp",
    "Microsoft.MixedReality.Portal", "Microsoft.MicrosoftSolitaireCollection"
]

# Serviços de telemetria e rastreamento


BLOAT_SERVICES = [
    "DiagTrack",          # Experiências do Usuário Conectado e Telemetria
    "dmwappushservice",   # Roteamento de Mensagens WAP Push (Telemetria)
    "SysMain",            # Antigo Superfetch (Gera escrita constante no Pagefile)
    "WSearch",            # Windows Search (Indexador que consome RAM em idle)
    "TabletInputService", # Teclado Virtual e Painel de Manuscrito
    "MapsBroker",         # Gerenciador de Mapas Baixados
    "XblAuthManager",     # Xbox Live Auth
    "XblGameSave",        # Xbox Live Save
    "XboxNetApiSvc",      # Xbox Live Networking
]