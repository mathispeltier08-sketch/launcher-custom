import os
import sys
import json
import ssl
import shutil
import zipfile
import urllib.request
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

import certifi
import minecraft_launcher_lib

# Certificats HTTPS
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

# --- CONFIGURATION DU SERVEUR ---
NOM_SERVEUR = "Manille et Mathis"
VERSION_MC = "1.12.2"
URL_PACK_ZIP = "https://worldofdisneycraft.fr/packserveurs.zip"
DOSSIER_NOM = ".manille-et-mathis"
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
        self.root.geometry("420x270")
        self.root.resizable(False, False)
        self.root.configure(bg="#1E162B")

        icone_path = chemin_ressource("icone.ico")
        if os.path.exists(icone_path):
            try:
                self.root.iconbitmap(icone_path)
            except Exception:
                pass

        self.config = self.charger_config()

        header_frame = tk.Frame(root, bg="#1E162B")
        header_frame.pack(fill="x", padx=15, pady=(12, 0))

        btn_params = tk.Button(
            header_frame,
            text="⚙ Paramètres",
            font=("Segoe UI", 9),
            bg="#2E2242",
            fg="#D8C8F0",
            activebackground="#43325E",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=3,
            command=self.ouvrir_parametres,
        )
        btn_params.pack(side="right")

        tk.Label(
            root,
            text=NOM_SERVEUR,
            font=("Segoe UI", 20, "bold"),
            bg="#1E162B",
            fg="#FFFFFF",
        ).pack(pady=(5, 18))

        tk.Label(
            root,
            text="PSEUDO EN JEU",
            font=("Segoe UI", 9, "bold"),
            bg="#1E162B",
            fg="#B79EE0",
        ).pack()

        self.entry_pseudo = tk.Entry(
            root,
            font=("Segoe UI", 13),
            justify="center",
            bg="#2E2242",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            width=22,
        )
        self.entry_pseudo.pack(pady=(6, 18), ipady=6)
        self.entry_pseudo.insert(0, self.config.get("pseudo", ""))

        self.btn_jouer = tk.Button(
            root,
            text="JOUER",
            font=("Segoe UI", 13, "bold"),
            bg="#8A4FFF",
            fg="#FFFFFF",
            activebackground="#7238E8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=20,
            command=self.demarrer_lancement,
        )
        self.btn_jouer.pack(ipady=6)

        self.label_statut = tk.Label(
            root,
            text="Prêt à jouer",
            font=("Segoe UI", 9),
            bg="#1E162B",
            fg="#A694C2",
        )
        self.label_statut.pack(pady=(12, 0))

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
        tk.Checkbutton(
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
        ).pack(pady=(8, 12))

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
        self.root.after(0, lambda: self.label_statut.config(text=texte))

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

    @staticmethod
    def noms_mods_du_zip(zf):
        """Retourne exactement les .jar contenus dans le dossier mods du ZIP."""
        mods = set()
        for info in zf.infolist():
            chemin = info.filename.replace("\\", "/").lstrip("/")
            morceaux = chemin.split("/")
            if len(morceaux) == 2 and morceaux[0].lower() == "mods":
                nom = morceaux[1]
                if nom.lower().endswith(".jar"):
                    mods.add(nom)
        return mods

    @staticmethod
    def extraire_zip_securise(zf, destination):
        """Bloque les chemins ZIP qui tentent de sortir du dossier du jeu."""
        destination_reelle = os.path.realpath(destination)
        for info in zf.infolist():
            cible = os.path.realpath(os.path.join(destination, info.filename))
            if os.path.commonpath([destination_reelle, cible]) != destination_reelle:
                raise RuntimeError(f"Chemin dangereux détecté dans le pack : {info.filename}")
        zf.extractall(destination)

    @staticmethod
    def verifier_mods(mods_autorises):
        """Refuse tout mod absent du ZIP officiel et tout mod officiel manquant."""
        dossier_mods = os.path.join(DOSSIER_JEU, "mods")
        if not os.path.isdir(dossier_mods):
            raise RuntimeError("Le dossier mods est introuvable après extraction du pack.")

        mods_presents = {
            fichier
            for fichier in os.listdir(dossier_mods)
            if os.path.isfile(os.path.join(dossier_mods, fichier))
            and fichier.lower().endswith(".jar")
        }

        ajoutes = sorted(mods_presents - mods_autorises)
        manquants = sorted(mods_autorises - mods_presents)

        if ajoutes:
            raise RuntimeError("Mod(s) non autorisé(s) : " + ", ".join(ajoutes))
        if manquants:
            raise RuntimeError("Mod(s) officiel(s) manquant(s) : " + ", ".join(manquants))

    def synchroniser_pack(self):
        self.maj_statut("Téléchargement des mods et configurations...")
        os.makedirs(DOSSIER_JEU, exist_ok=True)
        zip_temp = os.path.join(DOSSIER_JEU, "packserveurs_temp.zip")

        ctx = ssl.create_default_context(cafile=certifi.where())
        req = urllib.request.Request(URL_PACK_ZIP, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx) as resp, open(zip_temp, "wb") as out:
            shutil.copyfileobj(resp, out)

        try:
            self.maj_statut("Contrôle du pack officiel...")
            with zipfile.ZipFile(zip_temp, "r") as zf:
                fichier_invalide = zf.testzip()
                if fichier_invalide:
                    raise RuntimeError(f"Le pack ZIP est corrompu : {fichier_invalide}")

                mods_autorises = self.noms_mods_du_zip(zf)
                if not mods_autorises:
                    raise RuntimeError("Aucun mod .jar trouvé dans le dossier mods du pack.")

                self.maj_statut("Extraction et mise à jour des fichiers...")
                for dossier in ["mods", "config", "fancymenu_data", "fancymenu_setups"]:
                    cible = os.path.join(DOSSIER_JEU, dossier)
                    if os.path.exists(cible):
                        shutil.rmtree(cible, ignore_errors=True)

                self.extraire_zip_securise(zf, DOSSIER_JEU)

            self.maj_statut("Vérification des mods autorisés...")
            self.verifier_mods(mods_autorises)
        finally:
            if os.path.exists(zip_temp):
                os.remove(zip_temp)

    def demarrer_lancement(self):
        pseudo = self.entry_pseudo.get().strip()
        if not pseudo:
            messagebox.showwarning("Pseudo manquant", "Veuillez entrer un pseudo avant de jouer.")
            return

        self.config["pseudo"] = pseudo
        self.sauvegarder_config()
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

            # Le dossier mods est remplacé par celui du ZIP, puis sa liste est contrôlée.
            self.synchroniser_pack()

            self.maj_statut("Lancement du jeu...")
            ram_go = self.config.get("ram", 4)
            afficher_logs = self.config.get("logs", False)

            options = {
                "username": pseudo,
                "uuid": "",
                "token": "",
                "jvmArguments": [f"-Xmx{ram_go}G", "-Xms2G"],
            }

            commande = minecraft_launcher_lib.command.get_minecraft_command(
                version_id, DOSSIER_JEU, options
            )

            if afficher_logs:
                if sys.platform == "win32":
                    subprocess.Popen(
                        commande,
                        cwd=DOSSIER_JEU,
                        creationflags=subprocess.CREATE_NEW_CONSOLE,
                    )
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
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Erreur", f"Une erreur est survenue : {err_msg}"
                ),
            )
            self.root.after(
                0,
                lambda: self.btn_jouer.config(state="normal", bg="#8A4FFF"),
            )
            self.maj_statut("Prêt à jouer")


if __name__ == "__main__":
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()
