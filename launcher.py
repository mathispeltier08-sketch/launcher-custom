import os
import sys
import json
import ssl
import shutil
import zipfile
import urllib.request
import urllib.parse
import webbrowser
import io
import subprocess
import threading
import tempfile
import hashlib
from datetime import datetime, timezone
import tkinter as tk
from tkinter import messagebox

import certifi
import minecraft_launcher_lib
from PIL import Image, ImageTk, ImageEnhance

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

NOM_SERVEUR = "Manille et Mathis"
VERSION_MC = "1.12.2"
VERSION_LAUNCHER = "1.0.10"
URL_PACK_ZIP = "https://worldofdisneycraft.fr/packserveurs.zip"
URL_UPDATE_JSON = "https://raw.githubusercontent.com/mathispeltier08-sketch/launcher-custom/main/update.json"
URL_EVENEMENT_JSON = "https://raw.githubusercontent.com/mathispeltier08-sketch/launcher-custom/main/evenement.json"
URL_INSCRIPTION = "https://manille.djmathis.fr/user/register"
DOSSIER_NOM = ".manille-et-mathis"


def chemin_ressource(nom):
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, nom)


def obtenir_dossier_jeu():
    base = minecraft_launcher_lib.utils.get_minecraft_directory()
    return os.path.join(os.path.dirname(base), DOSSIER_NOM)


DOSSIER_JEU = obtenir_dossier_jeu()
FICHIER_CONFIG = os.path.join(DOSSIER_JEU, "launcher_config.json")


class BoutonArrondi(tk.Canvas):
    def __init__(self, parent, texte, commande, largeur=210, hauteur=44,
                 couleur="#49315F", survol="#60427A", texte_couleur="#FFFFFF",
                 rayon=18, police=("Segoe UI", 10, "bold")):
        super().__init__(parent, width=largeur, height=hauteur, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, cursor="hand2")
        self.largeur, self.hauteur, self.rayon = largeur, hauteur, rayon
        self.couleur, self.survol = couleur, survol
        self.texte, self.commande, self.police = texte, commande, police
        self.texte_couleur = texte_couleur
        self.actif = True
        self._dessiner(couleur)
        self.bind("<Enter>", lambda e: self._dessiner(self.survol) if self.actif else None)
        self.bind("<Leave>", lambda e: self._dessiner(self.couleur) if self.actif else None)
        self.bind("<Button-1>", self._clic)

    def _forme(self, couleur):
        w, h, r = self.largeur, self.hauteur, self.rayon
        self.create_rectangle(r, 1, w-r, h-1, fill=couleur, outline="")
        self.create_rectangle(1, r, w-1, h-r, fill=couleur, outline="")
        self.create_oval(1, 1, 2*r, 2*r, fill=couleur, outline="")
        self.create_oval(w-2*r, 1, w-1, 2*r, fill=couleur, outline="")
        self.create_oval(1, h-2*r, 2*r, h-1, fill=couleur, outline="")
        self.create_oval(w-2*r, h-2*r, w-1, h-1, fill=couleur, outline="")

    def _dessiner(self, couleur):
        self.delete("all")
        self._forme(couleur if self.actif else "#443B4D")
        self.create_text(self.largeur/2, self.hauteur/2, text=self.texte,
                         fill=self.texte_couleur if self.actif else "#93899D",
                         font=self.police)

    def _clic(self, event=None):
        if self.actif and self.commande:
            self._dessiner("#754EB0")
            self.after(90, lambda: self._dessiner(self.survol))
            self.commande()

    def configurer(self, texte=None, actif=None):
        if texte is not None:
            self.texte = texte
        if actif is not None:
            self.actif = actif
        self._dessiner(self.couleur)


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title(NOM_SERVEUR)
        self.root.geometry("1000x640")
        self.root.minsize(860, 560)
        self.root.configure(bg="#101018")

        ico = chemin_ressource("icone.ico")
        if os.path.exists(ico):
            try: self.root.iconbitmap(ico)
            except Exception: pass

        self.config = self.charger_config()
        self.fond_original = None
        self.fond_tk = None
        self.logo_tk = None
        self.avatar_tk = None
        self.bg_interface_label = None
        self.zone_background = None
        self.page_active = "jouer"
        self.cible_evenement = None
        self.apres_decompte = None

        self.canvas = tk.Canvas(root, bg="#101018", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.charger_images()

        self.interface = tk.Frame(self.canvas, bg="#15131D")
        self.fenetre_interface = self.canvas.create_window(0, 0, anchor="nw", window=self.interface)
        self.root.bind("<Configure>", self.redimensionner)

        if self.config.get("pseudo", "").strip():
            self.afficher_interface_connectee()
        else:
            self.afficher_bienvenue()

        self.creer_ecran_chargement()
        self.root.after(250, self.demarrer_verification_mise_a_jour)

    def charger_images(self):
        fond = chemin_ressource("fond_anniversaire.png")
        logo = chemin_ressource("logo.png")
        if os.path.exists(fond):
            image = Image.open(fond).convert("RGB")
            self.fond_original = ImageEnhance.Brightness(image).enhance(0.42)
        if os.path.exists(logo):
            image = Image.open(logo).convert("RGBA")
            image.thumbnail((220, 130), Image.Resampling.LANCZOS)
            self.logo_tk = ImageTk.PhotoImage(image)

    def redimensionner(self, event=None):
        w, h = max(1, self.root.winfo_width()), max(1, self.root.winfo_height())
        self.canvas.itemconfig(self.fenetre_interface, width=w, height=h)
        if self.fond_original:
            ratio = max(w/self.fond_original.width, h/self.fond_original.height)
            taille = (int(self.fond_original.width*ratio), int(self.fond_original.height*ratio))
            img = self.fond_original.resize(taille, Image.Resampling.LANCZOS)
            x, y = max(0, (img.width-w)//2), max(0, (img.height-h)//2)
            img = img.crop((x, y, x+w, y+h))
            self.fond_tk = ImageTk.PhotoImage(img)
            if hasattr(self, "fond_id"):
                self.canvas.itemconfig(self.fond_id, image=self.fond_tk)
            else:
                self.fond_id = self.canvas.create_image(0, 0, anchor="nw", image=self.fond_tk)
                self.canvas.tag_lower(self.fond_id)
            if self.bg_interface_label is not None and self.bg_interface_label.winfo_exists():
                self.bg_interface_label.config(image=self.fond_tk)
            if self.zone_background is not None and self.zone_background.winfo_exists():
                self.zone_background.config(image=self.fond_tk)

    def vider_interface(self):
        if self.apres_decompte:
            try: self.root.after_cancel(self.apres_decompte)
            except Exception: pass
            self.apres_decompte = None
        for widget in self.interface.winfo_children():
            widget.destroy()

    def logo(self, parent, pady=(20, 20)):
        if self.logo_tk:
            tk.Label(parent, image=self.logo_tk, bg=parent.cget("bg"), bd=0).pack(pady=pady)

    def afficher_bienvenue(self):
        self.vider_interface()
        panneau = tk.Frame(self.interface, bg="#17141F", highlightthickness=1,
                           highlightbackground="#4B3A60")
        panneau.place(relx=.5, rely=.5, anchor="center", width=400, height=390)
        self.logo(panneau, (42, 38))
        self.entree_pseudo = tk.Entry(panneau, font=("Segoe UI", 13), justify="center",
            bg="#262130", fg="#FFFFFF", insertbackground="#FFFFFF", relief="flat",
            highlightthickness=1, highlightbackground="#554567", highlightcolor="#956ECA")
        self.entree_pseudo.pack(ipady=10, ipadx=16, padx=54, fill="x", pady=(0, 20))
        self.entree_pseudo.bind("<Return>", lambda e: self.se_connecter())
        BoutonArrondi(panneau, "●  Se connecter", self.se_connecter, largeur=290,
                      couleur="#8253C7", survol="#9766DD").pack(pady=(0, 10))
        BoutonArrondi(panneau, "＋  Inscription", lambda: webbrowser.open(URL_INSCRIPTION),
                      largeur=290, couleur="#2B2536", survol="#443456").pack()

    def se_connecter(self):
        pseudo = self.entree_pseudo.get().strip()
        if not pseudo:
            messagebox.showwarning("Pseudo manquant", "Veuillez entrer un pseudo.")
            return
        self.config["pseudo"] = pseudo
        self.sauvegarder_config()
        self.afficher_interface_connectee()

    def afficher_interface_connectee(self):
        self.vider_interface()
        self.interface.configure(bg="#111019")
        self.bg_interface_label = tk.Label(self.interface, image=self.fond_tk, bg="#111019", bd=0)
        self.bg_interface_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.sidebar = tk.Frame(self.interface, bg="#17141F", width=245, highlightthickness=1, highlightbackground="#30283A")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.logo(self.sidebar, (20, 18))

        pseudo = self.config.get("pseudo", "")
        self.profil_frame = tk.Frame(self.sidebar, bg="#17141F")
        self.profil_frame.pack(pady=(0, 18))
        self.avatar_label = tk.Label(self.profil_frame, bg="#17141F", bd=0,
                                     width=52, height=52, compound="center")
        self.avatar_label.pack(side="left", padx=(0, 10))
        self.avatar_label.pack_propagate(False)
        tk.Label(self.profil_frame, text=pseudo, font=("Segoe UI", 13, "bold"),
                 bg="#17141F", fg="#FFFFFF").pack(side="left")
        threading.Thread(target=self.charger_tete_skin, args=(pseudo,), daemon=True).start()

        BoutonArrondi(self.sidebar, "⌂  Accueil", lambda: self.changer_page("jouer"),
                      couleur="#2B2536", survol="#443456").pack(pady=5)
        BoutonArrondi(self.sidebar, "⚙  Paramètres", lambda: self.changer_page("parametres"),
                      couleur="#2B2536", survol="#443456").pack(pady=5)
        BoutonArrondi(self.sidebar, "↪  Se déconnecter", self.se_deconnecter,
                      couleur="#2B2536", survol="#673B50").pack(side="bottom", pady=24)

        self.zone_droite = tk.Frame(self.interface, bg="#111019")
        self.zone_droite.pack(side="left", fill="both", expand=True)
        self.zone_background = tk.Label(self.zone_droite, image=self.fond_tk, bg="#111019", bd=0)
        self.zone_background.place(x=0, y=0, relwidth=1, relheight=1)
        self.contenu = tk.Frame(self.zone_droite, bg="#111019", highlightthickness=0)
        self.contenu.pack(fill="both", expand=True, padx=52, pady=(52, 126))

        self.footer = tk.Frame(self.zone_droite, bg="#17141F", height=88)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)
        self.label_statut = tk.Label(self.footer, text="", font=("Segoe UI", 9),
                                     bg="#17141F", fg="#BCA8D0")
        self.label_statut.pack(side="left", padx=28)
        self.btn_jouer = BoutonArrondi(self.footer, "▶  Jouer", self.demarrer_lancement,
                                       largeur=220, hauteur=48, couleur="#8253C7",
                                       survol="#9969DD", rayon=20,
                                       police=("Segoe UI", 12, "bold"))
        self.btn_jouer.pack(side="right", padx=30, pady=20)
        self.changer_page("jouer")
        self.animer_sidebar(0)

    def animer_sidebar(self, largeur):
        cible = 245
        largeur = min(cible, largeur + 25)
        self.sidebar.config(width=largeur)
        if largeur < cible:
            self.root.after(12, lambda: self.animer_sidebar(largeur))

    def changer_page(self, page):
        self.page_active = page
        for w in self.contenu.winfo_children(): w.destroy()
        if page == "jouer":
            self.afficher_page_jouer()
        elif page == "parametres":
            self.afficher_page_parametres()

    def charger_tete_skin(self, pseudo):
        try:
            nom = urllib.parse.quote(pseudo)
            url = f"https://api.mcskin.me/head/{nom}?size=96"
            req = urllib.request.Request(url, headers={"User-Agent": "Manille-et-Mathis-Launcher"})
            with urllib.request.urlopen(req, timeout=10) as reponse:
                image = Image.open(io.BytesIO(reponse.read())).convert("RGBA")
            # Uniformise toutes les réponses de l'API dans un carré exact 48 x 48.
            cote = min(image.width, image.height)
            gauche = max(0, (image.width - cote) // 2)
            haut = max(0, (image.height - cote) // 2)
            image = image.crop((gauche, haut, gauche + cote, haut + cote))
            image = image.resize((48, 48), Image.Resampling.NEAREST)
            cadre = Image.new("RGBA", (52, 52), (0, 0, 0, 0))
            cadre.paste(image, (2, 2), image)
            self.avatar_tk = ImageTk.PhotoImage(cadre)
            self.root.after(0, lambda: self.avatar_label.config(image=self.avatar_tk)
                            if self.avatar_label.winfo_exists() else None)
        except Exception:
            pass

    def afficher_page_parametres(self):
        panneau = tk.Frame(self.contenu, bg="#17141F")
        panneau.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Label(panneau, text="Paramètres", font=("Segoe UI", 22, "bold"),
                 bg="#17141F", fg="#FFFFFF").pack(pady=(18, 18))
        ram = tk.IntVar(value=self.config.get("ram", 4))
        valeur = tk.Label(panneau, text=f"Mémoire RAM : {ram.get()} Go",
                          font=("Segoe UI", 12, "bold"), bg="#17141F", fg="#BCA8D0")
        valeur.pack()
        tk.Scale(panneau, from_=2, to=16, orient="horizontal", variable=ram,
                 showvalue=False, length=300, bg="#17141F", fg="#FFFFFF",
                 troughcolor="#31283C", highlightthickness=0,
                 activebackground="#8253C7",
                 command=lambda v: valeur.config(text=f"Mémoire RAM : {int(float(v))} Go")).pack(pady=12)
        logs = tk.BooleanVar(value=self.config.get("logs", False))
        tk.Checkbutton(panneau, text="Afficher la console de logs", variable=logs,
                       font=("Segoe UI", 10), bg="#17141F", fg="#FFFFFF",
                       selectcolor="#2B2536", activebackground="#17141F",
                       activeforeground="#FFFFFF").pack(pady=8)
        def enregistrer():
            self.config.update(ram=ram.get(), logs=logs.get())
            self.sauvegarder_config()
            self.maj_statut("Paramètres enregistrés")
        BoutonArrondi(panneau, "✓  Enregistrer", enregistrer, largeur=220,
                      couleur="#8253C7", survol="#9766DD").pack(pady=14)

    def afficher_page_jouer(self):
        centre = tk.Frame(self.contenu, bg="#17141F", highlightthickness=1,
                          highlightbackground="#4B3A60")
        centre.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Label(centre, text="Prochain événement", font=("Segoe UI", 15),
                 bg="#17141F", fg="#BCA8D0").pack(pady=(0, 16))
        self.label_decompte = tk.Label(centre, text="Chargement…",
            font=("Segoe UI", 34, "bold"), bg="#17141F", fg="#FFFFFF")
        self.label_decompte.pack()
        self.label_date = tk.Label(centre, text="", font=("Segoe UI", 11),
                                   bg="#17141F", fg="#8F819E")
        self.label_date.pack(pady=(12, 0))
        threading.Thread(target=self.charger_evenement, daemon=True).start()

    def charger_evenement(self):
        try:
            req = urllib.request.Request(URL_EVENEMENT_JSON, headers={"User-Agent": "Launcher"})
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            cible = datetime.fromisoformat(data["date_heure"].replace("Z", "+00:00"))
            if cible.tzinfo is None: cible = cible.replace(tzinfo=timezone.utc)
            self.cible_evenement = cible
            texte = str(data.get("texte", ""))
            self.root.after(0, lambda: self.label_date.config(text=texte))
            self.root.after(0, self.actualiser_decompte)
        except Exception:
            self.root.after(0, lambda: self.label_decompte.config(text="Date indisponible"))

    def actualiser_decompte(self):
        if not self.cible_evenement or not self.label_decompte.winfo_exists(): return
        reste = self.cible_evenement - datetime.now(timezone.utc)
        secondes = max(0, int(reste.total_seconds()))
        if secondes == 0:
            texte = "C'est maintenant !"
        else:
            jours, secondes = divmod(secondes, 86400)
            heures, secondes = divmod(secondes, 3600)
            minutes, secondes = divmod(secondes, 60)
            texte = f"{jours:02d}j  {heures:02d}h  {minutes:02d}m  {secondes:02d}s"
        self.label_decompte.config(text=texte)
        self.apres_decompte = self.root.after(1000, self.actualiser_decompte)

    def se_deconnecter(self):
        self.config["pseudo"] = ""
        self.sauvegarder_config()
        self.afficher_bienvenue()

    def creer_ecran_chargement(self):
        self.chargement = tk.Frame(self.interface, bg="#111019")
        self.chargement.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.chargement.lift()
        self.label_update = tk.Label(self.chargement, text="Vérification…",
            font=("Segoe UI", 15, "bold"), bg="#17141F", fg="#FFFFFF")
        self.label_update.place(relx=.5, rely=.48, anchor="center")
        self.barre = tk.Canvas(self.chargement, width=320, height=8, bg="#292431",
                               highlightthickness=0)
        self.barre.place(relx=.5, rely=.55, anchor="center")
        self.barre_id = self.barre.create_rectangle(0, 0, 0, 8, fill="#8253C7", outline="")

    def maj_ecran_update(self, texte, pourcentage=0):
        def f():
            if self.chargement.winfo_exists():
                self.label_update.config(text=texte)
                self.barre.coords(self.barre_id, 0, 0, 3.2*max(0,min(100,pourcentage)), 8)
        self.root.after(0, f)

    @staticmethod
    def comparer_versions(a, b):
        def n(v): return [int(x) for x in str(v).strip().lstrip("vV").split(".")]
        a, b = n(a), n(b); l=max(len(a),len(b)); a += [0]*(l-len(a)); b += [0]*(l-len(b))
        return (a>b)-(a<b)

    @staticmethod
    def sha256(path):
        h=hashlib.sha256()
        with open(path,"rb") as f:
            for bloc in iter(lambda:f.read(1024*1024),b""): h.update(bloc)
        return h.hexdigest().lower()

    def demarrer_verification_mise_a_jour(self):
        threading.Thread(target=self.verifier_mise_a_jour, daemon=True).start()

    def verifier_mise_a_jour(self):
        try:
            self.maj_ecran_update("Vérification des mises à jour…", 10)
            req=urllib.request.Request(URL_UPDATE_JSON,headers={"User-Agent":"Launcher"})
            ctx=ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(req,context=ctx,timeout=15) as r:
                d=json.loads(r.read().decode("utf-8"))
            if self.comparer_versions(VERSION_LAUNCHER,d["version"])<0:
                self.telecharger_setup(d["version"],d["download_url"],d.get("sha256",""))
            else:
                self.root.after(250,self.chargement.destroy)
        except Exception as e:
            self.root.after(0,lambda:messagebox.showerror("Mise à jour",str(e)))

    def telecharger_setup(self, version, url, hash_attendu):
        fd,path=tempfile.mkstemp(prefix="launcher_setup_",suffix=".exe"); os.close(fd)
        req=urllib.request.Request(url,headers={"User-Agent":"Launcher"})
        ctx=ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req,context=ctx,timeout=120) as r,open(path,"wb") as out:
            total=int(r.headers.get("Content-Length",0) or 0); recu=0
            while True:
                bloc=r.read(262144)
                if not bloc: break
                out.write(bloc); recu+=len(bloc)
                self.maj_ecran_update(f"Téléchargement {version}…",10+(70*recu/total if total else 40))
        if hash_attendu and self.sha256(path)!=hash_attendu.lower(): raise RuntimeError("SHA-256 incorrect")
        self.lancer_setup(path)

    def lancer_setup(self, setup):
        if sys.platform!="win32": raise RuntimeError("Mise à jour automatique disponible sous Windows")
        exe=os.path.join(os.environ.get("LOCALAPPDATA",""),"Programs","ManilleEtMathisLauncher","launcher.exe")
        script=os.path.join(tempfile.gettempdir(),"maj_launcher.cmd")
        with open(script,"w",encoding="utf-8") as f:
            f.write("@echo off\r\ntimeout /t 2 /nobreak >nul\r\n")
            f.write(f'"{setup}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /SP-\r\n')
            f.write(f'timeout /t 1 /nobreak >nul\r\nstart "" "{exe}"\r\ndel /q "{setup}"\r\ndel /q "%~f0"\r\n')
        subprocess.Popen(["cmd","/c",script],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.root.after(250,self.root.destroy)

    def charger_config(self):
        try:
            with open(FICHIER_CONFIG,"r",encoding="utf-8") as f:return json.load(f)
        except Exception:return {"pseudo":"","ram":4,"logs":False}

    def sauvegarder_config(self):
        os.makedirs(DOSSIER_JEU,exist_ok=True)
        with open(FICHIER_CONFIG,"w",encoding="utf-8") as f:json.dump(self.config,f,indent=2)

    def ouvrir_parametres(self):
        win=tk.Toplevel(self.root); win.title("Paramètres"); win.geometry("360x250"); win.configure(bg="#17141F"); win.grab_set()
        tk.Label(win,text="Mémoire RAM",font=("Segoe UI",13,"bold"),bg="#17141F",fg="white").pack(pady=(24,8))
        ram=tk.IntVar(value=self.config.get("ram",4))
        valeur=tk.Label(win,text=f"{ram.get()} Go",bg="#17141F",fg="#BCA8D0",font=("Segoe UI",11)); valeur.pack()
        tk.Scale(win,from_=2,to=16,orient="horizontal",variable=ram,showvalue=False,length=250,bg="#17141F",troughcolor="#31283C",highlightthickness=0,command=lambda v:valeur.config(text=f"{int(float(v))} Go")).pack(pady=8)
        logs=tk.BooleanVar(value=self.config.get("logs",False))
        tk.Checkbutton(win,text="Afficher la console de logs",variable=logs,bg="#17141F",fg="white",selectcolor="#2B2536",activebackground="#17141F").pack(pady=5)
        def save(): self.config.update(ram=ram.get(),logs=logs.get()); self.sauvegarder_config(); win.destroy()
        BoutonArrondi(win,"Enregistrer",save,largeur=190,couleur="#8253C7",survol="#9766DD").pack(pady=12)

    def maj_statut(self, texte):
        self.root.after(0,lambda:self.label_statut.config(text=texte) if hasattr(self,"label_statut") and self.label_statut.winfo_exists() else None)

    def synchroniser_pack(self):
        self.maj_statut("Téléchargement du pack…"); os.makedirs(DOSSIER_JEU,exist_ok=True)
        temp=os.path.join(DOSSIER_JEU,"pack_temp.zip")
        req=urllib.request.Request(URL_PACK_ZIP,headers={"User-Agent":"Launcher"})
        ctx=ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req,context=ctx) as r,open(temp,"wb") as out: shutil.copyfileobj(r,out)
        for d in ["mods","config","fancymenu_data","fancymenu_setups"]:
            cible=os.path.join(DOSSIER_JEU,d)
            if os.path.exists(cible): shutil.rmtree(cible,ignore_errors=True)
        with zipfile.ZipFile(temp) as z:z.extractall(DOSSIER_JEU)
        os.remove(temp)

    def demarrer_lancement(self):
        pseudo=self.config.get("pseudo","").strip()
        if not pseudo:return
        self.btn_jouer.configurer("Préparation…",False)
        threading.Thread(target=self.processus_jeu,args=(pseudo,),daemon=True).start()

    def processus_jeu(self,pseudo):
        try:
            self.maj_statut("Vérification de Forge…")
            forge=minecraft_launcher_lib.forge.find_forge_version(VERSION_MC)
            if not forge: raise RuntimeError("Forge introuvable")
            version=f"{VERSION_MC}-forge-{forge.split('-',1)[1]}"
            if not os.path.exists(os.path.join(DOSSIER_JEU,"versions",version)):
                minecraft_launcher_lib.forge.install_forge_version(forge,DOSSIER_JEU,callback={"setStatus":self.maj_statut})
            self.synchroniser_pack(); self.maj_statut("Lancement du jeu…")
            opts={"username":pseudo,"uuid":"","token":"","jvmArguments":[f'-Xmx{self.config.get("ram",4)}G','-Xms2G']}
            cmd=minecraft_launcher_lib.command.get_minecraft_command(version,DOSSIER_JEU,opts)
            subprocess.Popen(cmd,cwd=DOSSIER_JEU,stdout=None if self.config.get("logs") else subprocess.DEVNULL,stderr=None if self.config.get("logs") else subprocess.DEVNULL)
            self.root.after(1200,self.root.destroy)
        except Exception as e:
            self.root.after(0,lambda:messagebox.showerror("Erreur",str(e)))
            self.root.after(0,lambda:self.btn_jouer.configurer("Jouer",True))


if __name__ == "__main__":
    root=tk.Tk(); app=LauncherApp(root); root.mainloop()
