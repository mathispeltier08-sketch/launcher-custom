import os
import sys
import json
import ssl
import shutil
import zipfile
import urllib.request
import subprocess
import threading
import tempfile
import hashlib
import urllib.parse
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageEnhance
import certifi
import minecraft_launcher_lib

# Forcer l'utilisation des certificats racine de certifi (corrige SSL: CERTIFICATE_VERIFY_FAILED sur Linux/macOS)
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

# --- CONFIGURATION DU SERVEUR ---
NOM_SERVEUR = "Manille et Mathis"
VERSION_MC = "1.12.2"
URL_PACK_ZIP = "https://worldofdisneycraft.fr/packserveurs.zip"
DOSSIER_NOM = ".manille-et-mathis"
VERSION_LAUNCHER = "1.0.7"
URL_UPDATE_JSON = "https://raw.githubusercontent.com/mathispeltier08-sketch/launcher-custom/main/update.json"
# --------------------------------

def chemin_ressource(nom_fichier):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, nom_fichier)
    return os.path.join(os.path.abspath("."), nom_fichier)

def obtenir_dossier_jeu():
    base = minecraft_launcher_lib.utils.get_minecraft_directory()
    return os.path.join(os.path.dirname(base), DOSSIER_NOM)

DOSSIER_JEU = obtenir_dossier_jeu()
FICHIER_CONFIG = os.path.join(DOSSIER_JEU, "launcher_config.json")

# Patch HTTPS pour les bibliotheques Minecraft 1.12.2
_ancienne_urlopen = urllib.request.urlopen
def _nouvelle_urlopen(url, *args, **kwargs):
    if isinstance(url, str) and url.startswith("http://libraries.minecraft.net"):
        url = url.replace("http://", "https://", 1)
    elif hasattr(url, "full_url") and url.full_url.startswith("http://libraries.minecraft.net"):
        url.full_url = url.full_url.replace("http://", "https://", 1)
    if "context" not in kwargs:
        kwargs["context"] = ssl.create_default_context(cafile=certifi.where())
    return _ancienne_urlopen(url, *args, **kwargs)
urllib.request.urlopen = _nouvelle_urlopen


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title(NOM_SERVEUR)
        self.root.geometry("900x560")
        self.root.minsize(760, 500)
        self.root.configure(bg="#160D22")

        icone_path = chemin_ressource("icone.ico")
        if os.path.exists(icone_path):
            try:
                self.root.iconbitmap(icone_path)
            except Exception:
                pass

        self.config = self.charger_config()
        self.image_fond_originale = None
        self.image_fond_tk = None
        self.logo_tk = None

        self.canvas = tk.Canvas(root, bg="#160D22", bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        fond_path = chemin_ressource("fond_anniversaire.png")
        if os.path.exists(fond_path):
            try:
                image = Image.open(fond_path).convert("RGB")
                self.image_fond_originale = ImageEnhance.Brightness(image).enhance(0.52)
            except Exception as erreur:
                print(f"Arrière-plan non chargé : {erreur}")

        logo_path = chemin_ressource("logo.png")
        if os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((220, 150), Image.Resampling.LANCZOS)
                self.logo_tk = ImageTk.PhotoImage(logo)
            except Exception as erreur:
                print(f"Logo non chargé : {erreur}")

        self.carte = tk.Frame(
            self.canvas,
            bg="#241535",
            bd=0,
            highlightthickness=1,
            highlightbackground="#5E4378",
        )
        self.carte_fenetre = self.canvas.create_window(
            450, 280, window=self.carte, width=390, height=430
        )

        # Le statut est recréé sur la page connectée, sous le bouton Jouer.
        self.label_statut = None

        pseudo = self.config.get("pseudo", "").strip()
        if pseudo:
            self.afficher_page_connectee()
        else:
            self.afficher_page_bienvenue()

        self.root.bind("<Configure>", self.redimensionner_interface)
        self.root.after(20, self.redimensionner_interface)
        self.creer_ecran_chargement()
        self.root.after(300, self.demarrer_verification_mise_a_jour)

    def vider_carte(self):
        for widget in self.carte.winfo_children():
            widget.destroy()
        self.label_statut = None

    def afficher_logo(self, parent, marge_haut=(35, 25)):
        if self.logo_tk is not None:
            tk.Label(
                parent,
                image=self.logo_tk,
                bg="#241535",
                bd=0,
            ).pack(pady=marge_haut)
        else:
            # Le logo doit être fourni sous le nom exact logo.png.
            tk.Frame(parent, bg="#241535", height=75).pack(fill="x", pady=(15, 5))

    def afficher_page_bienvenue(self):
        self.vider_carte()
        self.afficher_logo(self.carte, (30, 25))

        self.entry_pseudo = tk.Entry(
            self.carte,
            font=("Segoe UI", 13),
            justify="center",
            bg="#38234C",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            width=25,
            highlightthickness=1,
            highlightbackground="#725092",
            highlightcolor="#A877D1",
        )
        self.entry_pseudo.pack(pady=(0, 18), ipady=8)
        self.entry_pseudo.insert(0, "Pseudo")
        self.entry_pseudo.config(fg="#B8A7C9")

        def retirer_placeholder(event=None):
            if self.entry_pseudo.get() == "Pseudo":
                self.entry_pseudo.delete(0, "end")
                self.entry_pseudo.config(fg="#FFFFFF")

        def remettre_placeholder(event=None):
            if not self.entry_pseudo.get().strip():
                self.entry_pseudo.insert(0, "Pseudo")
                self.entry_pseudo.config(fg="#B8A7C9")

        self.entry_pseudo.bind("<FocusIn>", retirer_placeholder)
        self.entry_pseudo.bind("<FocusOut>", remettre_placeholder)
        self.entry_pseudo.bind("<Return>", lambda event: self.se_connecter())

        tk.Button(
            self.carte,
            text="Se connecter",
            font=("Segoe UI", 11, "bold"),
            bg="#8A4FFF",
            fg="#FFFFFF",
            activebackground="#A36BFF",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=22,
            command=self.se_connecter,
        ).pack(ipady=7)

    def se_connecter(self):
        pseudo = self.entry_pseudo.get().strip()
        if not pseudo or pseudo == "Pseudo":
            messagebox.showwarning("Pseudo manquant", "Veuillez entrer un pseudo.")
            return
        self.config["pseudo"] = pseudo
        self.sauvegarder_config()
        self.afficher_page_connectee()

    def afficher_page_connectee(self):
        self.vider_carte()
        self.afficher_logo(self.carte, (22, 18))

        pseudo = self.config.get("pseudo", "").strip()
        tk.Label(
            self.carte,
            text=pseudo,
            font=("Segoe UI", 15, "bold"),
            bg="#241535",
            fg="#FFFFFF",
        ).pack(pady=(0, 8))

        tk.Button(
            self.carte,
            text="Se déconnecter",
            font=("Segoe UI", 9),
            bg="#38234C",
            fg="#EADDF8",
            activebackground="#503268",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            command=self.se_deconnecter,
        ).pack(pady=(0, 22), ipadx=10, ipady=4)

        self.btn_jouer = tk.Button(
            self.carte,
            text="Jouer",
            font=("Segoe UI", 13, "bold"),
            bg="#8A4FFF",
            fg="#FFFFFF",
            activebackground="#A36BFF",
            activeforeground="#FFFFFF",
            disabledforeground="#C7B8DA",
            relief="flat",
            cursor="hand2",
            width=22,
            command=self.demarrer_lancement,
        )
        self.btn_jouer.pack(ipady=8)

        self.label_statut = tk.Label(
            self.carte,
            text="",
            font=("Segoe UI", 9),
            bg="#241535",
            fg="#CDB8E8",
        )
        self.label_statut.pack(pady=(8, 0))

        tk.Button(
            self.carte,
            text="Paramètres",
            font=("Segoe UI", 10),
            bg="#38234C",
            fg="#EADDF8",
            activebackground="#503268",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=22,
            command=self.ouvrir_parametres,
        ).pack(pady=(10, 0), ipady=6)

    def se_deconnecter(self):
        self.config["pseudo"] = ""
        self.sauvegarder_config()
        self.afficher_page_bienvenue()

    def redimensionner_interface(self, event=None):
        largeur = max(self.root.winfo_width(), 1)
        hauteur = max(self.root.winfo_height(), 1)
        self.canvas.coords(self.carte_fenetre, largeur // 2, hauteur // 2)

        if self.image_fond_originale is None:
            return

        ratio = max(
            largeur / self.image_fond_originale.width,
            hauteur / self.image_fond_originale.height,
        )
        taille = (
            max(1, int(self.image_fond_originale.width * ratio)),
            max(1, int(self.image_fond_originale.height * ratio)),
        )
        image = self.image_fond_originale.resize(taille, Image.Resampling.LANCZOS)
        gauche = max(0, (image.width - largeur) // 2)
        haut = max(0, (image.height - hauteur) // 2)
        image = image.crop((gauche, haut, gauche + largeur, haut + hauteur))
        self.image_fond_tk = ImageTk.PhotoImage(image)

        if hasattr(self, "fond_canvas"):
            self.canvas.itemconfig(self.fond_canvas, image=self.image_fond_tk)
        else:
            self.fond_canvas = self.canvas.create_image(
                0, 0, anchor="nw", image=self.image_fond_tk
            )
            self.canvas.tag_lower(self.fond_canvas)

    def creer_ecran_chargement(self):
        self.ecran_chargement = tk.Frame(self.carte, bg="#241535")
        self.ecran_chargement.place(x=0, y=0, relwidth=1, relheight=1)
        self.ecran_chargement.lift()

        tk.Label(
            self.ecran_chargement,
            text="Mise à jour du launcher",
            font=("Segoe UI", 20, "bold"),
            bg="#241535",
            fg="#FFFFFF",
        ).pack()
        self.label_update = tk.Label(
            self.ecran_chargement,
            text="Vérification des mises à jour…",
            font=("Segoe UI", 10),
            bg="#241535",
            fg="#DCCAF5",
        )
        self.label_update.pack(pady=(18, 12))

        self.canvas_progression = tk.Canvas(
            self.ecran_chargement, width=320, height=12,
            bg="#38234C", highlightthickness=0, bd=0
        )
        self.canvas_progression.pack()
        self.barre_progression = self.canvas_progression.create_rectangle(
            0, 0, 0, 12, fill="#8A4FFF", outline=""
        )
        self.pourcentage_update = tk.Label(
            self.ecran_chargement, text="", font=("Segoe UI", 9),
            bg="#241535", fg="#A993C2"
        )
        self.pourcentage_update.pack(pady=(8, 0))

    def maj_ecran_update(self, texte, pourcentage=None):
        def appliquer():
            self.label_update.config(text=texte)
            if pourcentage is None:
                self.pourcentage_update.config(text="")
            else:
                valeur = max(0, min(100, int(pourcentage)))
                self.canvas_progression.coords(self.barre_progression, 0, 0, 3.2 * valeur, 12)
                self.pourcentage_update.config(text=f"{valeur} %")
        self.root.after(0, appliquer)

    def terminer_ecran_chargement(self):
        self.maj_ecran_update("Launcher à jour", 100)
        self.root.after(450, self.ecran_chargement.destroy)

    @staticmethod
    def comparer_versions(a, b):
        def normaliser(v):
            valeurs = []
            for partie in str(v).strip().lstrip("vV").split("."):
                chiffres = "".join(c for c in partie if c.isdigit())
                valeurs.append(int(chiffres or 0))
            return valeurs
        va, vb = normaliser(a), normaliser(b)
        longueur = max(len(va), len(vb))
        va += [0] * (longueur - len(va))
        vb += [0] * (longueur - len(vb))
        return (va > vb) - (va < vb)

    @staticmethod
    def calculer_sha256(chemin):
        h = hashlib.sha256()
        with open(chemin, "rb") as fichier:
            for bloc in iter(lambda: fichier.read(1024 * 1024), b""):
                h.update(bloc)
        return h.hexdigest().lower()

    def demarrer_verification_mise_a_jour(self):
        threading.Thread(target=self.verifier_mise_a_jour, daemon=True).start()

    def verifier_mise_a_jour(self):
        try:
            self.maj_ecran_update("Vérification des mises à jour…", 5)
            ctx = ssl.create_default_context(cafile=certifi.where())
            req = urllib.request.Request(
                URL_UPDATE_JSON,
                headers={"User-Agent": "Manille-et-Mathis-Launcher"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=15) as reponse:
                donnees = json.loads(reponse.read().decode("utf-8"))

            version = str(donnees.get("version", "")).strip()
            url = str(donnees.get("download_url", "")).strip()
            sha256 = str(donnees.get("sha256", "")).strip().lower()

            if not version or not url:
                raise RuntimeError("Le fichier update.json est incomplet.")

            if self.comparer_versions(VERSION_LAUNCHER, version) < 0:
                self.telecharger_setup(version, url, sha256)
            else:
                self.root.after(0, self.terminer_ecran_chargement)
        except Exception as erreur:
            self.root.after(0, lambda: self.afficher_erreur_update(str(erreur)))

    def afficher_erreur_update(self, detail):
        self.maj_ecran_update("Mise à jour impossible", 0)
        messagebox.showerror(
            "Mise à jour obligatoire",
            "La mise à jour n'a pas pu être vérifiée ou installée.\n\n"
            "Vérifiez votre connexion Internet puis relancez le launcher.\n\n"
            f"Détail : {detail}",
        )
        self.root.destroy()

    def telecharger_setup(self, version, url, sha256_attendu):
        fichier_temp = None
        try:
            self.maj_ecran_update(f"Téléchargement de la version {version}…", 10)
            fd, fichier_temp = tempfile.mkstemp(prefix="launcher_setup_", suffix=".exe")
            os.close(fd)

            ctx = ssl.create_default_context(cafile=certifi.where())
            req = urllib.request.Request(
                url, headers={"User-Agent": "Manille-et-Mathis-Launcher"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=120) as reponse, open(fichier_temp, "wb") as sortie:
                taille = int(reponse.headers.get("Content-Length", 0) or 0)
                recu = 0
                while True:
                    bloc = reponse.read(1024 * 256)
                    if not bloc:
                        break
                    sortie.write(bloc)
                    recu += len(bloc)
                    progression = 10 + (70 * recu / taille) if taille else 45
                    self.maj_ecran_update(
                        f"Téléchargement de la version {version}…", progression
                    )

            if not os.path.getsize(fichier_temp):
                raise RuntimeError("Le setup téléchargé est vide.")

            self.maj_ecran_update("Vérification de la mise à jour…", 85)
            if sha256_attendu:
                sha256_recu = self.calculer_sha256(fichier_temp)
                if sha256_recu != sha256_attendu:
                    raise RuntimeError("Le contrôle SHA-256 du setup a échoué.")

            self.maj_ecran_update("Installation automatique…", 95)
            self.lancer_setup_silencieux(fichier_temp)
        except Exception:
            if fichier_temp and os.path.exists(fichier_temp):
                try:
                    os.remove(fichier_temp)
                except OSError:
                    pass
            raise

    def lancer_setup_silencieux(self, setup):
        if sys.platform != "win32":
            raise RuntimeError("La mise à jour automatique nécessite Windows.")

        # Le script attend que le launcher soit fermé avant d'installer.
        # Cela évite que le setup tente d'écraser des DLL encore utilisées.
        dossier_installation = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Programs",
            "ManilleEtMathisLauncher",
        )
        executable_installe = os.path.join(dossier_installation, "launcher.exe")
        script = os.path.join(tempfile.gettempdir(), "maj_manille_mathis.cmd")

        contenu = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            f'"{setup}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART '
            f'/CLOSEAPPLICATIONS /SP- /LOG="{setup}.log"\r\n'
            "if errorlevel 1 exit /b %errorlevel%\r\n"
            f'timeout /t 1 /nobreak >nul\r\n'
            f'start "" "{executable_installe}"\r\n'
            f'del /q "{setup}"\r\n'
            'del /q "%~f0"\r\n'
        )
        with open(script, "w", encoding="utf-8") as fichier:
            fichier.write(contenu)

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["cmd", "/c", script],
            creationflags=creationflags,
            close_fds=True,
        )
        self.maj_ecran_update("Installation de la mise à jour…", 100)
        self.root.after(250, self.root.destroy)

    def charger_config(self):
        if os.path.exists(FICHIER_CONFIG):
            try:
                with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"pseudo": "", "ram": 4, "logs": False}

    def sauvegarder_config(self):
        os.makedirs(DOSSIER_JEU, exist_ok=True)
        with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def ouvrir_parametres(self):
        win = tk.Toplevel(self.root)
        win.title("Paramètres")
        win.geometry("330x235")
        win.resizable(False, False)
        win.configure(bg="#1E162B")
        win.transient(self.root)
        win.grab_set()

        icone_path = chemin_ressource("icone.ico")
        if os.path.exists(icone_path):
            try:
                win.iconbitmap(icone_path)
            except Exception:
                pass

        tk.Label(
            win,
            text="Mémoire RAM allouée (Go)",
            font=("Segoe UI", 11, "bold"),
            bg="#1E162B",
            fg="#FFFFFF",
        ).pack(pady=(15, 5))

        ram_var = tk.IntVar(value=self.config.get("ram", 4))
        lbl_valeur = tk.Label(
            win,
            text=f"{ram_var.get()} Go",
            font=("Segoe UI", 12, "bold"),
            bg="#1E162B",
            fg="#B79EE0",
        )
        lbl_valeur.pack()

        def maj_label(val):
            lbl_valeur.config(text=f"{int(float(val))} Go")

        scale = tk.Scale(
            win,
            from_=2,
            to=16,
            orient="horizontal",
            variable=ram_var,
            showvalue=False,
            bg="#1E162B",
            fg="#FFFFFF",
            troughcolor="#2E2242",
            highlightthickness=0,
            activebackground="#8A4FFF",
            length=230,
            command=maj_label,
        )
        scale.pack(pady=6)

        logs_var = tk.BooleanVar(value=self.config.get("logs", False))
        chk_logs = tk.Checkbutton(
            win,
            text="Afficher la console de logs au lancement",
            variable=logs_var,
            font=("Segoe UI", 9),
            bg="#1E162B",
            fg="#D8C8F0",
            selectcolor="#2E2242",
            activebackground="#1E162B",
            activeforeground="#FFFFFF",
            highlightthickness=0,
            cursor="hand2",
        )
        chk_logs.pack(pady=(8, 12))

        def valider():
            self.config["ram"] = int(ram_var.get())
            self.config["logs"] = bool(logs_var.get())
            self.sauvegarder_config()
            win.destroy()

        tk.Button(
            win,
            text="Enregistrer",
            font=("Segoe UI", 10, "bold"),
            bg="#8A4FFF",
            fg="#FFFFFF",
            activebackground="#7238E8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=14,
            command=valider,
        ).pack(ipady=3)

    def maj_statut(self, texte):
        def appliquer():
            if self.label_statut is not None and self.label_statut.winfo_exists():
                self.label_statut.config(text=texte)
        self.root.after(0, appliquer)

    def nettoyer_fichiers_vides(self):
        dossier_lib = os.path.join(DOSSIER_JEU, "libraries")
        if not os.path.exists(dossier_lib):
            return
        for racine, _, fichiers in os.walk(dossier_lib):
            for fichier in fichiers:
                chemin = os.path.join(racine, fichier)
                try:
                    if os.path.getsize(chemin) == 0:
                        os.remove(chemin)
                except Exception:
                    pass

    def synchroniser_pack(self):
        self.maj_statut("Téléchargement des mods et configurations...")
        os.makedirs(DOSSIER_JEU, exist_ok=True)
        zip_temp = os.path.join(DOSSIER_JEU, "packserveurs_temp.zip")

        ctx = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(URL_PACK_ZIP, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx) as resp, open(zip_temp, "wb") as out:
            shutil.copyfileobj(resp, out)

        self.maj_statut("Extraction et mise à jour des fichiers...")
        for dossier in ["mods", "config", "fancymenu_data", "fancymenu_setups"]:
            cible = os.path.join(DOSSIER_JEU, dossier)
            if os.path.exists(cible):
                shutil.rmtree(cible, ignore_errors=True)

        with zipfile.ZipFile(zip_temp, "r") as zf:
            zf.extractall(DOSSIER_JEU)

        if os.path.exists(zip_temp):
            os.remove(zip_temp)

    def demarrer_lancement(self):
        pseudo = self.config.get("pseudo", "").strip()
        if not pseudo:
            self.afficher_page_bienvenue()
            return

        self.btn_jouer.config(state="disabled", bg="#563899")
        threading.Thread(target=self.processus_jeu, args=(pseudo,), daemon=True).start()

    def processus_jeu(self, pseudo):
        try:
            self.nettoyer_fichiers_vides()

            self.maj_statut("Vérification de Forge 1.12.2...")
            forge_version = minecraft_launcher_lib.forge.find_forge_version(VERSION_MC)
            if not forge_version:
                raise RuntimeError("Impossible de trouver la version Forge 1.12.2.")

            version_id = f"{VERSION_MC}-forge-{forge_version.split('-', 1)[1]}"
            dossier_version = os.path.join(DOSSIER_JEU, "versions", version_id)

            if not os.path.exists(dossier_version):
                self.maj_statut("Installation de Minecraft & Forge (patientez)...")
                callback = {"setStatus": lambda text: self.maj_statut(text)}
                minecraft_launcher_lib.forge.install_forge_version(
                    forge_version, DOSSIER_JEU, callback=callback
                )

            self.synchroniser_pack()

            self.maj_statut("Lancement du jeu...")
            ram_go = self.config.get("ram", 4)
            afficher_logs = self.config.get("logs", False)

            options = {
                "username": pseudo,
                "uuid": "",
                "token": "",
                "jvmArguments": [f"-Xmx{ram_go}G", f"-Xms2G"],
            }

            commande = minecraft_launcher_lib.command.get_minecraft_command(
                version_id, DOSSIER_JEU, options
            )

            if afficher_logs:
                if sys.platform == "win32":
                    subprocess.Popen(commande, cwd=DOSSIER_JEU, creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    subprocess.Popen(commande, cwd=DOSSIER_JEU)
            else:
                kwargs = {
                    "cwd": DOSSIER_JEU,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                    "stdin": subprocess.DEVNULL,
                }
                if sys.platform == "win32":
                    kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(commande, **kwargs)

            self.root.after(1500, self.root.destroy)

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Erreur", f"Une erreur est survenue : {err_msg}"))
            self.root.after(0, lambda: self.btn_jouer.config(state="normal", bg="#8A4FFF"))
            self.maj_statut("Prêt à jouer")


if __name__ == "__main__":
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()
