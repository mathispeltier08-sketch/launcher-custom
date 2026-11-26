import os
import sys
import json
import shutil
import zipfile
import urllib.request
import threading
import subprocess
import tkinter as tk
from tkinter import messagebox
import minecraft_launcher_lib

# ==========================================
# CONFIGURATION DU SERVEUR
# ==========================================
NOM_SERVEUR = "Manille et Mathis"
VERSION_MC = "1.12.2"
DOSSIER_NOM = ".manille-et-mathis"
URL_PACK_ZIP = "https://worldofdisneycraft.fr/packserveurs.zip"
RAM_DEFAUT = 4

# ==========================================
# CHEMINS ET PARAMETRES
# ==========================================
DOSSIER_JEU = minecraft_launcher_lib.utils.get_minecraft_directory().replace(".minecraft", DOSSIER_NOM)
FICHIER_CONFIG = os.path.join(DOSSIER_JEU, "launcher_config.json")


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def charger_config():
    if os.path.exists(FICHIER_CONFIG):
        try:
            with open(FICHIER_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"pseudo": "", "ram": RAM_DEFAUT, "logs": False}


def sauvegarder_config(data):
    os.makedirs(DOSSIER_JEU, exist_ok=True)
    with open(FICHIER_CONFIG, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def nettoyer_bibliotheques_vides():
    lib_dir = os.path.join(DOSSIER_JEU, "libraries")
    if not os.path.exists(lib_dir):
        return
    for root_dir, _, files in os.walk(lib_dir):
        for file in files:
            chemin = os.path.join(root_dir, file)
            try:
                if os.path.getsize(chemin) == 0:
                    os.remove(chemin)
            except Exception:
                pass


def patch_https_requests():
    import requests
    old_request = requests.Session.request

    def new_request(self, method, url, *args, **kwargs):
        if isinstance(url, str) and url.startswith("http://libraries.minecraft.net"):
            url = url.replace("http://", "https://", 1)
        return old_request(self, method, url, *args, **kwargs)

    requests.Session.request = new_request


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title(NOM_SERVEUR)
        self.root.geometry("420x310")
        self.root.resizable(False, False)
        self.root.configure(bg="#1E162B")

        icone_path = resource_path("icone.ico")
        if os.path.exists(icone_path):
            try:
                self.root.iconbitmap(icone_path)
            except Exception:
                pass

        self.config = charger_config()
        self.ram_var = tk.IntVar(value=self.config.get("ram", RAM_DEFAUT))
        self.logs_var = tk.BooleanVar(value=self.config.get("logs", False))
        self.en_cours = False

        self.creer_interface()

    def creer_interface(self):
        # Barre superieure avec bouton Parametres
        top_bar = tk.Frame(self.root, bg="#1E162B")
        top_bar.pack(fill="x", padx=15, pady=(12, 0))

        btn_params = tk.Button(
            top_bar,
            text="⚙ Paramètres",
            font=("Segoe UI", 9, "bold"),
            bg="#2E2242",
            fg="#D8C8F0",
            activebackground="#43325E",
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=3,
            command=self.ouvrir_parametres
        )
        btn_params.pack(side="right")

        # Titre principal
        tk.Label(
            self.root,
            text=NOM_SERVEUR,
            font=("Segoe UI", 21, "bold"),
            bg="#1E162B",
            fg="#FFFFFF"
        ).pack(pady=(12, 22))

        # Label Pseudo
        tk.Label(
            self.root,
            text="Entrez votre pseudo Minecraft :",
            font=("Segoe UI", 10),
            bg="#1E162B",
            fg="#C8B6E2"
        ).pack(pady=(0, 6))

        # Champ Pseudo
        self.entry_pseudo = tk.Entry(
            self.root,
            font=("Segoe UI", 13, "bold"),
            justify="center",
            bg="#2E2242",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
            width=22
        )
        self.entry_pseudo.pack(ipady=7)
        self.entry_pseudo.insert(0, self.config.get("pseudo", ""))
        self.entry_pseudo.bind("<Return>", lambda e: self.demarrer())

        # Bouton Jouer
        self.btn_jouer = tk.Button(
            self.root,
            text="JOUER",
            font=("Segoe UI", 13, "bold"),
            bg="#7B2CBF",
            fg="#FFFFFF",
            activebackground="#9D4EDD",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=18,
            command=self.demarrer
        )
        self.btn_jouer.pack(pady=(22, 12), ipady=6)

        # Statut
        self.lbl_statut = tk.Label(
            self.root,
            text="Prêt à jouer",
            font=("Segoe UI", 9),
            bg="#1E162B",
            fg="#A695C2"
        )
        self.lbl_statut.pack()

    def ouvrir_parametres(self):
        fenetre_params = tk.Toplevel(self.root)
        fenetre_params.title("Paramètres")
        fenetre_params.geometry("340x255")
        fenetre_params.resizable(False, False)
        fenetre_params.configure(bg="#1E162B")
        fenetre_params.transient(self.root)
        fenetre_params.grab_set()

        icone_path = resource_path("icone.ico")
        if os.path.exists(icone_path):
            try:
                fenetre_params.iconbitmap(icone_path)
            except Exception:
                pass

        tk.Label(
            fenetre_params,
            text="Mémoire RAM allouée",
            font=("Segoe UI", 12, "bold"),
            bg="#1E162B",
            fg="#FFFFFF"
        ).pack(pady=(15, 5))

        lbl_ram_val = tk.Label(
            fenetre_params,
            text=f"{self.ram_var.get()} Go",
            font=("Segoe UI", 11, "bold"),
            bg="#1E162B",
            fg="#C77DFF"
        )
        lbl_ram_val.pack(pady=(0, 4))

        def maj_label_ram(val):
            lbl_ram_val.config(text=f"{int(float(val))} Go")

        scale_ram = tk.Scale(
            fenetre_params,
            from_=2,
            to=16,
            orient="horizontal",
            variable=self.ram_var,
            showvalue=False,
            length=230,
            bg="#1E162B",
            fg="#FFFFFF",
            troughcolor="#2E2242",
            activebackground="#9D4EDD",
            highlightthickness=0,
            command=maj_label_ram
        )
        scale_ram.pack(pady=4)

        # Case a cocher Logs a l'ouverture
        chk_logs = tk.Checkbutton(
            fenetre_params,
            text="Afficher la console de logs au lancement",
            variable=self.logs_var,
            font=("Segoe UI", 9),
            bg="#1E162B",
            fg="#D8C8F0",
            selectcolor="#2E2242",
            activebackground="#1E162B",
            activeforeground="#FFFFFF",
            cursor="hand2"
        )
        chk_logs.pack(pady=(12, 8))

        def valider_params():
            self.config["ram"] = int(self.ram_var.get())
            self.config["logs"] = bool(self.logs_var.get())
            sauvegarder_config(self.config)
            fenetre_params.destroy()

        tk.Button(
            fenetre_params,
            text="Enregistrer",
            font=("Segoe UI", 10, "bold"),
            bg="#7B2CBF",
            fg="#FFFFFF",
            activebackground="#9D4EDD",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            width=14,
            command=valider_params
        ).pack(pady=(8, 0), ipady=4)

    def maj_statut(self, texte):
        self.root.after(0, lambda: self.lbl_statut.config(text=texte))

    def demarrer(self):
        if self.en_cours:
            return

        pseudo = self.entry_pseudo.get().strip()
        if not pseudo or len(pseudo) < 3 or len(pseudo) > 16:
            messagebox.showwarning("Pseudo invalide", "Veuillez entrer un pseudo valide (3 à 16 caractères).")
            return

        self.config["pseudo"] = pseudo
        self.config["ram"] = int(self.ram_var.get())
        self.config["logs"] = bool(self.logs_var.get())
        sauvegarder_config(self.config)

        self.en_cours = True
        self.btn_jouer.config(state="disabled", bg="#4A3B63")
        self.entry_pseudo.config(state="disabled")

        threading.Thread(target=self.processus_lancement, args=(pseudo,), daemon=True).start()

    def synchroniser_pack(self):
        self.maj_statut("Téléchargement des mods et configurations...")
        zip_temp = os.path.join(DOSSIER_JEU, "packserveurs_temp.zip")
        os.makedirs(DOSSIER_JEU, exist_ok=True)

        req = urllib.request.Request(URL_PACK_ZIP, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(zip_temp, "wb") as out_file:
            shutil.copyfileobj(response, out_file)

        self.maj_statut("Mise à jour des fichiers du serveur...")
        for dossier in ["mods", "config", "fancymenu_data", "fancymenu_setups"]:
            chemin_cible = os.path.join(DOSSIER_JEU, dossier)
            if os.path.exists(chemin_cible):
                shutil.rmtree(chemin_cible, ignore_errors=True)

        with zipfile.ZipFile(zip_temp, "r") as zip_ref:
            zip_ref.extractall(DOSSIER_JEU)

        if os.path.exists(zip_temp):
            os.remove(zip_temp)

    def processus_lancement(self, pseudo):
        try:
            patch_https_requests()
            nettoyer_bibliotheques_vides()

            self.maj_statut("Vérification de Minecraft 1.12.2...")
            minecraft_launcher_lib.install.install_minecraft_version(VERSION_MC, DOSSIER_JEU)

            forge_version = minecraft_launcher_lib.forge.find_forge_version(VERSION_MC)
            version_complete = f"{VERSION_MC}-forge-{forge_version.split('-')[1]}"
            dossier_version_forge = os.path.join(DOSSIER_JEU, "versions", version_complete)

            if not os.path.exists(dossier_version_forge):
                self.maj_statut("Installation de Forge 1.12.2 (patientez)...")
                minecraft_launcher_lib.forge.install_forge_version(forge_version, DOSSIER_JEU)

            self.synchroniser_pack()

            self.maj_statut("Lancement du jeu...")
            ram_go = int(self.config.get("ram", RAM_DEFAUT))
            afficher_logs = bool(self.config.get("logs", False))

            options = {
                "username": pseudo,
                "uuid": "",
                "token": "",
                "jvmArguments": [f"-Xmx{ram_go}G", f"-Xms2G"]
            }

            commande = minecraft_launcher_lib.command.get_minecraft_command(
                version_complete, DOSSIER_JEU, options
            )

            if afficher_logs:
                if os.name == "nt":
                    subprocess.Popen(
                        commande,
                        cwd=DOSSIER_JEU,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    subprocess.Popen(commande, cwd=DOSSIER_JEU)
            else:
                popen_kwargs = {
                    "cwd": DOSSIER_JEU,
                    "stdout": subprocess.DEVNULL,
                    "stderr": subprocess.DEVNULL,
                    "stdin": subprocess.DEVNULL,
                }
                if os.name == "nt":
                    popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(commande, **popen_kwargs)

            self.root.after(1500, self.root.destroy)

        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Erreur", "Une erreur est survenue : " + err_msg))
            self.root.after(0, self.reinitialiser_ui)

    def reinitialiser_ui(self):
        self.en_cours = False
        self.btn_jouer.config(state="normal", bg="#7B2CBF")
        self.entry_pseudo.config(state="normal")
        self.maj_statut("Prêt à jouer")


if __name__ == "__main__":
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()
