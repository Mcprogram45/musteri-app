# -*- coding: utf-8 -*-
"""
Müşteri Takip — Android sürümü (Kivy)
- Müşteri kaydı, ürün bazlı satış, hesap takibi, borç hatırlatma
- Veritabanı: telefonun kendi içinde musteriler.db olarak saklanır
"""

import os
import sqlite3
import datetime
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem


def para(x):
    return f"{x:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def bugun():
    return datetime.date.today()


class DB:
    def __init__(self, yol):
        self.yol = yol
        self.kur()

    def baglan(self):
        con = sqlite3.connect(self.yol)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def kur(self):
        con = self.baglan()
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS musteriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL, telefon TEXT, adres TEXT, olusturma TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS urunler (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL, fiyat REAL NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS hareketler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            musteri_id INTEGER NOT NULL, tarih TEXT, aciklama TEXT,
            tutar REAL NOT NULL, tip TEXT NOT NULL, vade TEXT,
            FOREIGN KEY (musteri_id) REFERENCES musteriler(id) ON DELETE CASCADE)""")
        cols = [r[1] for r in cur.execute("PRAGMA table_info(hareketler)")]
        if "vade" not in cols:
            cur.execute("ALTER TABLE hareketler ADD COLUMN vade TEXT")
        con.commit()
        con.close()

    def bakiye(self, con, mid):
        return con.execute(
            "SELECT COALESCE(SUM(CASE tip WHEN 'borc' THEN tutar ELSE -tutar END),0) "
            "FROM hareketler WHERE musteri_id=?", (mid,)).fetchone()[0]

    def odendi_mi(self, mid, hid):
        con = self.baglan()
        row = con.execute("SELECT vade FROM hareketler WHERE id=?", (hid,)).fetchone()
        if not row or not row[0]:
            con.close()
            return False
        vade = row[0]
        odeme = con.execute(
            "SELECT COALESCE(SUM(tutar),0) FROM hareketler "
            "WHERE musteri_id=? AND tip='odeme' AND tarih>=?",
            (mid, vade + " 00:00")).fetchone()[0]
        con.close()
        return odeme > 0


class MusteriApp(App):
    def build(self):
        self.title = "Müşteri Takip"
        taban = getattr(self, "user_data_dir", None) or "."
        self.db = DB(os.path.join(taban, "musteriler.db"))

        self.panel = TabbedPanel(do_default_tab=False, tab_height=48)
        self.tab_mus = TabbedPanelItem(text="Müşteriler")
        self.tab_urun = TabbedPanelItem(text="Ürünler")
        self.tab_hesap = TabbedPanelItem(text="Hesap")
        self.tab_hat = TabbedPanelItem(text="Hatırlatma")
        self.tab_mus.add_widget(self.musteri_sekmesi())
        self.tab_urun.add_widget(self.urun_sekmesi())
        self.tab_hesap.add_widget(self.hesap_sekmesi())
        self.tab_hat.add_widget(self.hatirlatma_sekmesi())
        for t in (self.tab_mus, self.tab_urun, self.tab_hesap, self.tab_hat):
            self.panel.add_widget(t)

        self.hepsini_yukle()
        return self.panel

    # ---------- yardımcılar ----------
    def uyari(self, mesaj, baslik="Uyarı"):
        Popup(title=baslik, content=Label(text=mesaj),
              size_hint=(0.85, 0.28)).open()

    def onay(self, mesaj, evet_fonksiyonu):
        icerik = BoxLayout(orientation="vertical", padding=6, spacing=6)
        icerik.add_widget(Label(text=mesaj))
        satir = BoxLayout(size_hint_y=None, height=48, spacing=8)
        p = Popup(title="Onay", content=icerik, size_hint=(0.85, 0.32))
        satir.add_widget(Button(text="Evet", on_release=lambda i: (p.dismiss(), evet_fonksiyonu())))
        satir.add_widget(Button(text="Vazgeç", on_release=p.dismiss))
        icerik.add_widget(satir)
        p.open()

    def satir(self, metin, butonlar=None, renk=(1, 1, 1, 1), boy=56):
        k = BoxLayout(size_hint_y=None, height=boy, spacing=4)
        ana = Button(text=metin, halign="left", valign="middle", markup=True,
                     background_normal="", background_color=renk)
        ana.bind(size=lambda i, v: setattr(i, "text_size", (v[0] - 12, v[1] - 8)))
        k.add_widget(ana)
        for yazi, fonk in (butonlar or []):
            bt = Button(text=yazi, size_hint_x=None, width=70)
            bt.bind(on_release=fonk)
            k.add_widget(bt)
        return k

    def liste_kutusu(self):
        kutu = GridLayout(cols=1, spacing=4, size_hint_y=None, padding=(0, 2))
        kutu.bind(minimum_height=kutu.setter("height"))
        kaydir = ScrollView(do_scroll_x=False)
        kaydir.add_widget(kutu)
        return kutu, kaydir

    def hepsini_yukle(self):
        self.musterileri_yukle()
        self.urunleri_yukle()
        self.hareketleri_yukle()
        self.hatirlatmalari_yukle()

    # ---------- sekme 1: müşteriler ----------
    def musteri_sekmesi(self):
        govde = BoxLayout(orientation="vertical", padding=6, spacing=6)
        s1 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.in_m_ad = TextInput(hint_text="Ad Soyad", multiline=False)
        self.in_m_tel = TextInput(hint_text="Telefon", multiline=False,
                                  input_type="tel", size_hint_x=0.6)
        s1.add_widget(self.in_m_ad)
        s1.add_widget(self.in_m_tel)
        govde.add_widget(s1)
        s2 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.in_m_adres = TextInput(hint_text="Adres", multiline=False)
        b = Button(text="Kaydet", size_hint_x=0.4)
        b.bind(on_release=lambda i: self.musteri_ekle())
        s2.add_widget(self.in_m_adres)
        s2.add_widget(b)
        govde.add_widget(s2)
        self.in_ara = TextInput(hint_text="Ara (ad, telefon, adres)",
                                multiline=False, size_hint_y=None, height=44)
        self.in_ara.bind(text=lambda i, v: self.musterileri_yukle())
        govde.add_widget(self.in_ara)
        self.mus_listesi, kaydir = self.liste_kutusu()
        govde.add_widget(kaydir)
        return govde

    def musteri_ekle(self):
        ad = self.in_m_ad.text.strip()
        if not ad:
            self.uyari("Ad Soyad boş olamaz!")
            return
        con = self.db.baglan()
        con.execute("INSERT INTO musteriler (ad, telefon, adres, olusturma) VALUES (?,?,?,?)",
                    (ad, self.in_m_tel.text.strip(), self.in_m_adres.text.strip(),
                     datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
        con.commit()
        con.close()
        self.in_m_ad.text = ""
        self.in_m_tel.text = ""
        self.in_m_adres.text = ""
        self.hepsini_yukle()

    def musterileri_yukle(self):
        ara = self.in_ara.text.strip()
        con = self.db.baglan()
        if ara:
            rows = con.execute("SELECT id, ad, telefon, adres FROM musteriler "
                               "WHERE ad LIKE ? OR telefon LIKE ? OR adres LIKE ? ORDER BY ad",
                               (f"%{ara}%",) * 3).fetchall()
        else:
            rows = con.execute("SELECT id, ad, telefon, adres FROM musteriler ORDER BY ad").fetchall()
        self.mus_listesi.clear_widgets()
        self.mus_map = {}
        etiketler = []
        b_iso = bugun().isoformat()
        for mid, ad, tel, adres in rows:
            bak = self.db.bakiye(con, mid)
            renk = (1.0, 0.82, 0.82, 1) if bak > 0 else (0.94, 0.97, 1.0, 1)
            ek = f" | {adres}" if adres else ""
            self.mus_listesi.add_widget(self.satir(
                f"[b]{ad}[/b]  No:{mid}\n{tel or chr(45)} | Bakiye: {para(bak)}{ek}",
                [("Hesap", partial(self.musteriye_git, mid, ad)),
                 ("Sil", partial(self.musteri_sil, mid))], renk))
            etiket = f"{ad} (No:{mid})"
            etiketler.append(etiket)
            self.mus_map[etiket] = mid
        con.close()
        self.sp_mus.values = etiketler
        if self.sp_mus.text != "Müşteri seçin…" and self.sp_mus.text not in self.mus_map:
            self.sp_mus.text = "Müşteri seçin…"
            self.hareketleri_yukle()

    def musteriye_git(self, mid, ad, *args):
        etiket = f"{ad} (No:{mid})"
        if etiket in (self.sp_mus.values or []):
            self.sp_mus.text = etiket
        self.hareketleri_yukle()
        self.panel.switch_to(self.tab_hesap)

    def musteri_sil(self, mid, *args):
        self.onay("Müşteri ve tüm hesap hareketleri silinsin mi?",
                  partial(self._musteri_sil, mid))

    def _musteri_sil(self, mid):
        con = self.db.baglan()
        con.execute("DELETE FROM musteriler WHERE id=?", (mid,))
        con.commit()
        con.close()
        self.hepsini_yukle()

    # ---------- sekme 2: ürünler ----------
    def urun_sekmesi(self):
        govde = BoxLayout(orientation="vertical", padding=6, spacing=6)
        sat = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.in_u_ad = TextInput(hint_text="Ürün adı", multiline=False)
        self.in_u_fiyat = TextInput(hint_text="Birim fiyat (TL)", multiline=False,
                                    size_hint_x=0.55)
        b = Button(text="Kaydet", size_hint_x=0.4)
        b.bind(on_release=lambda i: self.urun_ekle())
        sat.add_widget(self.in_u_ad)
        sat.add_widget(self.in_u_fiyat)
        sat.add_widget(b)
        govde.add_widget(sat)
        self.urun_listesi, kaydir = self.liste_kutusu()
        govde.add_widget(kaydir)
        return govde

    def urun_ekle(self):
        ad = self.in_u_ad.text.strip()
        try:
            fiyat = float(self.in_u_fiyat.text.replace(",", "."))
            if not ad or fiyat < 0:
                raise ValueError
        except ValueError:
            self.uyari("Geçerli bir ürün adı ve fiyat girin! (örn. 250 veya 250,50)")
            return
        con = self.db.baglan()
        con.execute("INSERT INTO urunler (ad, fiyat) VALUES (?,?)", (ad, fiyat))
        con.commit()
        con.close()
        self.in_u_ad.text = ""
        self.in_u_fiyat.text = ""
        self.urunleri_yukle()

    def urunleri_yukle(self):
        con = self.db.baglan()
        rows = con.execute("SELECT id, ad, fiyat FROM urunler ORDER BY ad").fetchall()
        con.close()
        self.urun_listesi.clear_widgets()
        self.urun_map = {}
        etiketler = []
        for uid, ad, fiyat in rows:
            self.urun_listesi.add_widget(self.satir(
                f"[b]{ad}[/b]\nBirim fiyat: {para(fiyat)}",
                [("Sil", partial(self.urun_sil, uid))], (0.94, 1.0, 0.94, 1)))
            etiket = f"{ad} — {para(fiyat)}"
            etiketler.append(etiket)
            self.urun_map[etiket] = (uid, ad, fiyat)
        self.sp_urun.values = etiketler
        self.tutar_guncelle()

    def urun_sil(self, uid, *args):
        self.onay("Seçili ürün silinsin mi? (Eski satışlar etkilenmez)",
                  partial(self._urun_sil, uid))

    def _urun_sil(self, uid):
        con = self.db.baglan()
        con.execute("DELETE FROM urunler WHERE id=?", (uid,))
        con.commit()
        con.close()
        self.urunleri_yukle()

    # ---------- sekme 3: hesap takibi ----------
    def hesap_sekmesi(self):
        govde = BoxLayout(orientation="vertical", padding=6, spacing=6)
        s1 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.sp_mus = Spinner(text="Müşteri seçin…", size_hint_x=0.65)
        self.sp_mus.bind(text=lambda i, v: self.hareketleri_yukle())
        self.lbl_bakiye = Label(text="Bakiye: -", size_hint_x=0.45)
        s1.add_widget(self.sp_mus)
        s1.add_widget(self.lbl_bakiye)
        govde.add_widget(s1)

        kutu = GridLayout(cols=1, spacing=4, size_hint_y=None, padding=(0, 2))
        kutu.bind(minimum_height=kutu.setter("height"))
        kutu.add_widget(Label(text="— Ürün Satışı —", size_hint_y=None, height=28,
                              color=(0.3, 0.3, 0.3, 1)))
        s2 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.sp_urun = Spinner(text="Ürün seçin…")
        self.sp_urun.bind(text=lambda i, v: self.tutar_guncelle())
        self.in_adet = TextInput(hint_text="Adet", multiline=False,
                                 input_type="number", size_hint_x=0.3)
        self.in_adet.bind(text=lambda i, v: self.tutar_guncelle())
        self.lbl_tutar = Label(text="-", size_hint_x=0.4)
        s2.add_widget(self.sp_urun)
        s2.add_widget(self.in_adet)
        s2.add_widget(self.lbl_tutar)
        kutu.add_widget(s2)
        s3 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        b1 = Button(text="Veresiye Sat (Borç)")
        b1.bind(on_release=lambda i: self.urun_sat("borc"))
        b2 = Button(text="Peşin Sat (Ödeme)")
        b2.bind(on_release=lambda i: self.urun_sat("odeme"))
        s3.add_widget(b1)
        s3.add_widget(b2)
        kutu.add_widget(s3)
        kutu.add_widget(Label(text="— Manuel Hareket —", size_hint_y=None, height=28,
                              color=(0.3, 0.3, 0.3, 1)))
        s4 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.in_acik = TextInput(hint_text="Açıklama", multiline=False)
        self.in_tutar = TextInput(hint_text="Tutar (TL)", multiline=False, size_hint_x=0.5)
        s4.add_widget(self.in_acik)
        s4.add_widget(self.in_tutar)
        kutu.add_widget(s4)
        s5 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.in_vade = TextInput(hint_text="Hatırlatma GG.AA.YYYY", multiline=False)
        b3 = Button(text="Borç Ekle", size_hint_x=0.42)
        b3.bind(on_release=lambda i: self.hareket_ekle("borc"))
        b4 = Button(text="Ödeme Al", size_hint_x=0.42)
        b4.bind(on_release=lambda i: self.hareket_ekle("odeme"))
        s5.add_widget(self.in_vade)
        s5.add_widget(b3)
        s5.add_widget(b4)
        kutu.add_widget(s5)
        kaydir_form = ScrollView(size_hint_y=None, height=290, do_scroll_x=False)
        kaydir_form.add_widget(kutu)
        govde.add_widget(kaydir_form)

        self.har_listesi, kaydir = self.liste_kutusu()
        govde.add_widget(kaydir)
        return govde

    def tutar_guncelle(self):
        bilgi = self.urun_map.get(self.sp_urun.text)
        if not bilgi:
            self.lbl_tutar.text = "-"
            return
        try:
            adet = int(self.in_adet.text or 1)
            if adet < 1:
                adet = 1
        except ValueError:
            adet = 1
        self.lbl_tutar.text = para(round(bilgi[2] * adet, 2))

    def urun_sat(self, tip):
        mid = self.mus_map.get(self.sp_mus.text)
        if not mid:
            self.uyari("Önce bir müşteri seçin! (Müşteriler sekmesindeki 'Hesap' düğmesini kullanabilirsiniz.)")
            return
        bilgi = self.urun_map.get(self.sp_urun.text)
        if not bilgi:
            self.uyari("Önce bir ürün seçin!")
            return
        try:
            adet = int(self.in_adet.text)
            if adet < 1:
                raise ValueError
        except ValueError:
            self.uyari("Geçerli bir adet girin!")
            return
        uid, ad, fiyat = bilgi
        tutar = round(fiyat * adet, 2)
        self.hareket_kaydet(mid, f"{ad} x{adet} (No:{uid})", tutar, tip)
        self.in_adet.text = ""
        self.tutar_guncelle()

    def vade_oku(self):
        v = self.in_vade.text.strip()
        if not v:
            return None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
        raise ValueError("Hatırlatma tarihi GG.AA.YYYY formatında olmalı (örn. 15.12.2026)")

    def hareket_kaydet(self, mid, aciklama, tutar, tip, vade=None):
        con = self.db.baglan()
        con.execute("INSERT INTO hareketler (musteri_id, tarih, aciklama, tutar, tip, vade) "
                    "VALUES (?,?,?,?,?,?)",
                    (mid, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                     aciklama, tutar, tip, vade))
        con.commit()
        con.close()
        self.hareketleri_yukle()
        self.musterileri_yukle()
        self.hatirlatmalari_yukle()

    def hareket_ekle(self, tip):
        mid = self.mus_map.get(self.sp_mus.text)
        if not mid:
            self.uyari("Önce bir müşteri seçin!")
            return
        try:
            tutar = float(self.in_tutar.text.replace(",", "."))
            if tutar <= 0:
                raise ValueError
        except ValueError:
            self.uyari("Geçerli bir tutar girin (örn. 250 veya 250,50)")
            return
        try:
            vade = self.vade_oku()
        except ValueError as e:
            self.uyari(str(e))
            return
        acik = self.in_acik.text.strip() or ("Satış" if tip == "borc" else "Ödeme")
        self.hareket_kaydet(mid, acik, tutar, tip, vade)
        self.in_tutar.text = ""
        self.in_acik.text = ""
        self.in_vade.text = ""

    def hareketleri_yukle(self):
        self.har_listesi.clear_widgets()
        mid = self.mus_map.get(self.sp_mus.text)
        if not mid:
            self.lbl_bakiye.text = "Bakiye: -"
            return
        b_iso = bugun().isoformat()
        con = self.db.baglan()
        rows = con.execute("SELECT id, tarih, aciklama, tutar, tip, vade FROM hareketler "
                           "WHERE musteri_id=? ORDER BY id DESC", (mid,)).fetchall()
        bak = self.db.bakiye(con, mid)
        con.close()
        for hid, tarih, acik, tutar, tip, vade in rows:
            gecikti = (tip == "borc" and vade and vade < b_iso
                       and not self.db.odendi_mi(mid, hid))
            renk = (1.0, 0.78, 0.78, 1) if gecikti else (1, 1, 1, 1)
            tur = "Borç" if tip == "borc" else "Ödeme"
            vade_txt = f"\nHatırlatma: {vade}" if vade else ""
            self.har_listesi.add_widget(self.satir(
                f"{tarih}  |  [b]{tur}:[/b] {para(tutar)}\n{acik}{vade_txt}",
                [("Sil", partial(self.hareket_sil, hid))], renk, boy=72))
        durum = " (alacaklısınız)" if bak > 0 else (" (borçlusunuz)" if bak < 0 else "")
        self.lbl_bakiye.text = f"Bakiye: {para(bak)}{durum}"

    def hareket_sil(self, hid, *args):
        self.onay("Seçili hareket silinsin mi?", partial(self._hareket_sil, hid))

    def _hareket_sil(self, hid):
        con = self.db.baglan()
        con.execute("DELETE FROM hareketler WHERE id=?", (hid,))
        con.commit()
        con.close()
        self.hareketleri_yukle()
        self.musterileri_yukle()
        self.hatirlatmalari_yukle()

    # ---------- sekme 4: hatırlatmalar ----------
    def hatirlatma_sekmesi(self):
        govde = BoxLayout(orientation="vertical", padding=6, spacing=6)
        sat = BoxLayout(size_hint_y=None, height=44, spacing=4)
        sat.add_widget(Label(text="Vadesi geçen veya 7 gün içinde dolacak borçlar"))
        b = Button(text="Yenile", size_hint_x=0.3)
        b.bind(on_release=lambda i: self.hatirlatmalari_yukle())
        sat.add_widget(b)
        govde.add_widget(sat)
        self.hat_listesi, kaydir = self.liste_kutusu()
        govde.add_widget(kaydir)
        return govde

    def hatirlatmalari_yukle(self):
        self.hat_listesi.clear_widgets()
        bug = bugun()
        sinir = (bug + datetime.timedelta(days=7)).isoformat()
        b_iso = bug.isoformat()
        con = self.db.baglan()
        rows = con.execute("""SELECT m.ad, h.tarih, h.aciklama, h.tutar, h.vade, h.id, h.musteri_id
            FROM hareketler h JOIN musteriler m ON m.id = h.musteri_id
            WHERE h.tip='borc' AND h.vade IS NOT NULL AND h.vade <= ? ORDER BY h.vade""",
                           (sinir,)).fetchall()
        con.close()
        if not rows:
            self.hat_listesi.add_widget(self.satir("Yaklaşan veya gecikmiş borç yok. ✔",
                                                   renk=(0.9, 1.0, 0.9, 1)))
        for ad, tarih, acik, tutar, vade, hid, mid in rows:
            gecikti = vade < b_iso and not self.db.odendi_mi(mid, hid)
            if gecikti:
                durum = "VADESİ GEÇTİ ❗"
                renk = (1.0, 0.72, 0.72, 1)
            else:
                gun = (datetime.date.fromisoformat(vade) - bug).days
                durum = f"{gun} gün kaldı"
                renk = (1.0, 0.94, 0.75, 1)
            self.hat_listesi.add_widget(self.satir(
                f"[b]{ad}[/b] — {acik}\n{para(tutar)}  |  Vade: {vade}  |  {durum}",
                [("Hesap", partial(self.musteriye_git, mid, ad))], renk, boy=72))


if __name__ == "__main__":
    MusteriApp().run()
