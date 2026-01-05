
Ce guide détaille toutes les étapes pour installer et configurer Rex-Brain sur ton PC Windows et ton téléphone Android.

## 📋 Ce dont tu auras besoin

### Comptes à créer (gratuits avec crédits ou pay-as-you-go)

| Service | URL | Utilisation | Coût estimé |
|---------|-----|-------------|-------------|
| **Deepgram** | https://console.deepgram.com/ | Speech-to-text | $200 crédits gratuits |
| **OpenAI** | https://platform.openai.com/ | Text-to-speech | ~$5/mois |
| **Anthropic** | https://console.anthropic.com/ | LLM + Vision | ~$20-40/mois |

### Sur ton PC Windows

- Python 3.11 (pas 3.12, problèmes de compatibilité)
- Git
- ~10 GB d'espace disque (pour Android SDK)

### Sur ton téléphone Android

- Mode développeur activé
- Débogage USB activé
- Câble USB

---

## 🚀 Étape 1: Installation de Python (Windows)

1. Télécharge Python 3.11 depuis https://www.python.org/downloads/
2. **IMPORTANT**: Coche "Add Python to PATH" pendant l'installation
3. Vérifie l'installation dans PowerShell:

```powershell
py --version
# Doit afficher: Python 3.11.x
```

> **Note**: Sur Windows, utilise `py` au lieu de `python` si `python` ne fonctionne pas.

---

## 🚀 Étape 2: Installation de Git

1. Télécharge Git depuis https://git-scm.com/download/win
2. Installe avec les options par défaut
3. Vérifie:

```powershell
git --version
```

---

## 🚀 Étape 3: Préparation du projet (Windows)

Ouvre PowerShell et exécute:

```powershell
# Aller dans le dossier du projet
cd C:\Users\flore\Documents\Cursor\rex

# Créer un environnement virtuel avec py (Python Launcher)
py -3.11 -m venv venv

# Installer pip dans le venv manuellement si nécessaire
.\venv\Scripts\python.exe -m ensurepip --upgrade

# Installer les dépendances
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

> **Si erreur de politique d'exécution**, exécute d'abord:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## 🚀 Étape 4: Configuration des clés API

### 4.1 Deepgram (Speech-to-Text)

1. Va sur https://console.deepgram.com/signup
2. Crée un compte (tu reçois $200 de crédits gratuits)
3. Va dans "API Keys" → "Create a New API Key"
4. Copie la clé

### 4.2 OpenAI (Text-to-Speech)

1. Va sur https://platform.openai.com/signup
2. Crée un compte et ajoute un moyen de paiement
3. Va dans "API Keys" → "Create new secret key"
4. Copie la clé

### 4.3 Anthropic Claude (LLM + Vision)

1. Va sur https://console.anthropic.com/
2. Crée un compte et ajoute un moyen de paiement
3. Va dans "API Keys" → "Create Key"
4. Copie la clé

### 4.4 Mettre les clés dans le projet

Édite le fichier `config/settings.yaml`:

```yaml
api_keys:
  deepgram: "ta-clé-deepgram-ici"
  openai: "ta-clé-openai-ici"
  anthropic: "ta-clé-anthropic-ici"
```

> ⚠️ **SÉCURITÉ**: Ce fichier est dans `.gitignore` et ne sera pas partagé sur GitHub. Ne partage jamais tes clés API !

---

## 🚀 Étape 5: Installation de WSL et Buildozer

Buildozer (pour créer l'APK Android) nécessite Linux. Sur Windows, on utilise WSL.

### 5.1 Installer WSL

Dans PowerShell **en mode Administrateur**:

```powershell
wsl --install
```

**Redémarre ton PC** après l'installation.

### 5.2 Configurer Ubuntu dans WSL

Après redémarrage, ouvre "**Ubuntu**" depuis le menu Démarrer. Crée un utilisateur quand demandé.

```bash
# Mettre à jour Ubuntu
sudo apt update && sudo apt upgrade -y

# Installer les dépendances système
sudo apt install -y software-properties-common git zip unzip openjdk-17-jdk \
    autoconf automake libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev cmake libffi-dev libssl-dev

# Ajouter le repo pour Python 3.11 (Ubuntu 24.04 a Python 3.12 par défaut)
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Installer Python 3.11
sudo apt install python3.11 python3.11-venv python3.11-dev -y
```

### 5.3 Créer un environnement pour Buildozer

```bash
# Créer un venv dédié à buildozer avec Python 3.11
python3.11 -m venv ~/buildozer-venv

# Activer le venv
source ~/buildozer-venv/bin/activate

# Installer buildozer et cython
pip install --upgrade pip
pip install buildozer cython==0.29.33

# Vérifier
buildozer --version
```

### 5.4 Configurer les permissions WSL (optionnel mais recommandé)

```bash
# Créer le fichier de config WSL
sudo nano /etc/wsl.conf
```

Ajoute ce contenu:

```ini
[automount]
enabled = true
options = "metadata,umask=22,fmask=11"

[interop]
enabled = true
appendWindowsPath = true
```

Sauvegarde (Ctrl+O, Enter, Ctrl+X) puis dans PowerShell Windows:

```powershell
wsl --shutdown
```

Relance Ubuntu.

---

## 🚀 Étape 6: Construction de l'APK

### 6.1 Première construction

Dans le terminal Ubuntu (WSL):

```bash
# Activer l'environnement buildozer
source ~/buildozer-venv/bin/activate

# Aller dans le projet
cd /mnt/c/Users/flore/Documents/Cursor/rex

# Lancer le build (30-60 minutes la première fois)
buildozer android debug
```

L'APK sera créé dans: `bin/rexbrain-0.1.0-arm64-v8a-debug.apk`

### 6.2 Temps de build selon les modifications

| Type de modification | Temps | Commande |
|---------------------|-------|----------|
| Code Python, images, prompts, config | **2-5 min** | `buildozer android debug` |
| Permissions, version | **10-20 min** | `buildozer android clean && buildozer android debug` |
| Nouvelle librairie Python | **20-30 min** | Supprimer le cache puis rebuild (voir ci-dessous) |
| Premier build / tout refaire | **30-60 min** | `rm -rf .buildozer && buildozer android debug` |

### 6.3 Commandes utiles

```bash
# Build normal (après modif de code)
buildozer android debug

# Nettoyer et rebuilder (après modif buildozer.spec)
buildozer android clean && buildozer android debug

# Supprimer le cache de compilation (après ajout de librairie)
rm -rf .buildozer/android/platform/build-arm64-v8a
buildozer android debug

# Tout refaire depuis zéro
rm -rf .buildozer
buildozer android debug
```

---

## 🚀 Étape 7: Installation sur le téléphone

### 7.1 Activer le mode développeur sur ton Zenphone 8

1. Va dans **Paramètres** → **À propos du téléphone**
2. Appuie 7 fois sur **Numéro de build**
3. Tu verras "Vous êtes maintenant développeur"

### 7.2 Activer le débogage USB

1. Va dans **Paramètres** → **Options pour les développeurs**
2. Active **Débogage USB**

### 7.3 Installer l'APK

**Option 1: Via ADB (dans WSL)**

```bash
# Installer ADB
sudo apt install android-tools-adb

# Vérifier que le téléphone est détecté
adb devices

# Installer l'APK
adb install bin/rexbrain-0.1.0-arm64-v8a-debug.apk
```

**Option 2: Manuellement**

1. Copie le fichier `.apk` sur ton téléphone (USB ou cloud)
2. Ouvre le fichier sur le téléphone
3. Autorise l'installation depuis des sources inconnues

---

## 🚀 Étape 8: Connexion au robot

Il y a deux façons de connecter le téléphone au robot :

### Option A: WiFi Connected Mode (recommandé pour commencer)

Le robot et le téléphone sont sur le même réseau WiFi maison.

1. Ouvre l'**app Unitree** sur ton téléphone
2. Connecte-toi au robot en **Bluetooth**
3. Va dans les paramètres et choisis **"WiFi Connected Mode"**
4. Connecte le Go2 à ton **WiFi maison**
5. **Note l'adresse IP** du robot (affichée dans l'app Unitree)
6. Mets cette IP dans `config/settings.yaml` :
   ```yaml
   connection:
     robot_ip: "192.168.1.XXX"  # L'IP de ton Go2
   ```
7. Assure-toi que le téléphone Rex est aussi sur le même WiFi maison
8. Lance Rex-Brain !

> ✅ **Avantage** : Le téléphone garde accès à Internet pour les APIs
> ❌ **Limite** : Fonctionne seulement à portée de ton WiFi maison

### Option B: AP Router Mode + 4G (pour l'extérieur)

Le robot crée son propre réseau WiFi, le téléphone s'y connecte tout en utilisant la 4G pour Internet.

1. Dans l'app Unitree, choisis **"AP Router Mode"**
2. Le robot crée un réseau **Go2-XXXXXX**
3. Mot de passe : **`00000000`** (8 zéros) ou pas de mot de passe
4. Mets une **carte SIM 4G** dans le téléphone
5. Connecte le téléphone au WiFi du robot (Go2-XXXXXX)
6. Le téléphone utilisera automatiquement la 4G pour Internet
7. Dans `config/settings.yaml` :
   ```yaml
   connection:
     robot_ip: "192.168.12.1"  # IP par défaut en mode AP
   ```
8. Lance Rex-Brain !

> ✅ **Avantage** : Fonctionne partout (parc, forêt, etc.)
> ❌ **Coût** : Nécessite un forfait 4G avec data

### 8.2 Lancer Rex-Brain

1. Lance l'application "Rex Brain" sur le téléphone
2. L'app devrait se connecter automatiquement au robot
3. Tu verras les logs s'afficher à l'écran

---

## 🔧 Dépannage

### "buildozer: command not found"

```bash
# Activer le venv buildozer
source ~/buildozer-venv/bin/activate
```

### "No module named 'distutils'"

Tu utilises Python 3.12 au lieu de 3.11. Recrée le venv avec Python 3.11:

```bash
rm -rf ~/buildozer-venv
python3.11 -m venv ~/buildozer-venv
source ~/buildozer-venv/bin/activate
pip install buildozer cython==0.29.33
```

### Erreur "externally-managed-environment"

N'utilise pas `pip install --user`, utilise un venv à la place (voir étape 5.3).

### Erreur de permissions sur /mnt/c/

Configure WSL correctement (voir étape 5.4) ou travaille dans le système de fichiers Linux:

```bash
# Copier le projet vers Linux
cp -r /mnt/c/Users/flore/Documents/Cursor/rex ~/projects/rex
cd ~/projects/rex
buildozer android debug

# Copier l'APK vers Windows après le build
cp bin/*.apk /mnt/c/Users/flore/Documents/Cursor/rex/bin/
```

### Le téléphone n'est pas détecté par ADB

1. Vérifie que le câble USB supporte les données (pas juste la charge)
2. Sur le téléphone, change le mode USB en "Transfert de fichiers"
3. Accepte le popup de débogage sur le téléphone

### L'app plante au démarrage

Regarde les logs:
```bash
adb logcat | grep python
```

---

## 📊 Estimation des coûts mensuels

Pour ~10h d'utilisation par mois:

| Service | Usage | Coût |
|---------|-------|------|
| Deepgram STT | ~10h audio | ~$2.50 |
| OpenAI TTS | ~5000 caractères/h | ~$7.50 |
| Claude LLM | ~500 requêtes | ~$15-25 |
| Claude Vision | ~2000 images | ~$5-10 |
| **TOTAL** | | **~30-45€/mois** |

Les premiers mois seront moins chers grâce aux crédits gratuits de Deepgram.

---

## 🔄 Workflow de développement quotidien

```bash
# 1. Ouvrir Ubuntu (WSL)
# 2. Activer l'environnement
source ~/buildozer-venv/bin/activate

# 3. Aller dans le projet
cd /mnt/c/Users/flore/Documents/Cursor/rex

# 4. Builder après modifications
buildozer android debug

# 5. Installer sur le téléphone
adb install -r bin/*.apk
```

> **Astuce**: Ajoute un alias dans `~/.bashrc`:
> ```bash
> echo 'alias rex-build="source ~/buildozer-venv/bin/activate && cd /mnt/c/Users/flore/Documents/Cursor/rex && buildozer android debug"' >> ~/.bashrc
> source ~/.bashrc
> ```
> Ensuite tu peux juste taper `rex-build` !

---

## 🎉 C'est parti !

Une fois tout installé:
1. Monte le téléphone sur le robot
2. Allume le robot
3. Connecte le téléphone au WiFi du robot
4. Lance Rex-Brain
5. Dis "Rex !" et commence à discuter !

Pour toute question ou problème, ouvre une issue sur GitHub.
