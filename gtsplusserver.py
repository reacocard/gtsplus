
from base64 import urlsafe_b64decode, urlsafe_b64encode
import hashlib
import time
import thread
import socket
import struct
import sqlite3
from BaseHTTPServer import *

import pkmutils
import pkmlib
import namemaps

DNS_SERVER = "8.8.8.8" # google's public DNS is speedy

STD_SERV_HEADERS = [
        ("Server", "Microsoft-IIS/6.0"),
        ("P3P", "CP='NOI ADMa OUR STP'"),
        ("cluster-server", "aphexweb3"),
        ("X-Server-Name", "AW4"),
        ("X-Powered-By", "ASP.NET"),
        ("Content-Type", "text/html"),
        ("Set-Cookie", "ASPSESSIONIDQCDBDDQS=JFDOAMPAGACBDMLNLFBCCNCI; path=/"),
        ("Cache-control", "private"),
    ]

GTS_SALT = "HZEdGCzcGGLvguqUEKQN"
GTS_TOKEN = "c9KcX1Cry3QKS2Ai7yxL6QiQGeBGeQKR"

SEND_QUEUE = []

SQL_POKEMON_FIELDS = [
        'personality',
        'species',
        'item',
        'otid',
        'otsecret',
        'ability',
        'attack1',
        'attack2',
        'attack3',
        'attack4',
        'isegg',
        'fateful',
        'gender',
        'forme',
        'nature',
        'dreamworld',
        'nickname',
        'otname',
        'pokerus',
        'pokeball',
        'otgender',
        'level',
        'shiny',
        ]


CONN = None

def open_db(filename):
    conn = sqlite3.connect(filename)
    c = conn.cursor()
    try:
        c.execute("""create table pokemon (
            sourcepid       text,
            personality     int,
            species         int,
            item            int,
            otid            int,
            otsecret        int,
            ability         int,
            attack1         int,
            attack2         int,
            attack3         int,
            attack4         int,
            isegg           bool,
            fateful         bool,
            gender          int,
            forme           int,
            nature          int,
            dreamworld      bool,
            nickname        text,
            otname          text,
            pokerus         int,
            pokeball        int,
            otgender        int,
            level           int,
            shiny           bool,
            pkm_struct      blob
            )""")
        conn.commit()
    except sqlite3.OperationalError:
        pass # DB was already created
    c.close()
    return conn

def add_pokemon(pkm, sourcepid):
    assert (len(pkm) == 220) # we only support gen V in-party .pkm files
    data = pkmutils.pkmtodata(pkm)
    values = [sourcepid] + [data[x] for x in SQL_POKEMON_FIELDS] + [buffer(pkm)]
    values = [buffer(x) if isinstance(x, str) else x for x in values]
    print values[:-1]
    c = CONN.cursor()
    c.execute("insert into pokemon values (?" + ",?"*(len(values)-1) + ")", values)
    CONN.commit()
    c.close()

def pkmtogts(pkm):
    bin  = '\x00' * 16
    bin += pkm[0x08:0x0a] # id
    if ord(pkm[0x40]) & 0x04: bin += '\x03' # Gender
    else: bin += chr((ord(pkm[0x40]) & 2) + 1)
    bin += pkm[0x8c] # Level
    bin += '\x01\x00\x03\x00\x00\x00\x00\x00' # Requesting bulba, either, any
    bin += '\xdb\x07\x03\x0a\x00\x00\x00\x00' # Date deposited (10 Mar 2011)
    bin += '\xdb\x07\x03\x16\x01\x30\x00\x00' # Date traded (?)
    bin += pkm[0x00:0x04] # PID
    bin += pkm[0x0c:0x0e] # OT ID
    bin += pkm[0x0e:0x10] # OT Secret ID
    bin += pkm[0x68:0x78] # OT Name
    bin += '\xDB\x02' # Country, City
    bin += '\x46\x01\x15\x02' # Sprite, Exchanged (?), Version, Lang
    bin += '\x01\x00' # Unknown

    return pkmlib.encode(pkm) + bin



def dnsspoof():
    # basic idea: forward everything to DNS_SERVER so we don't have to
    # make up our own replies, and rewrite the address in the reply if
    # the requested name is gamestats2.gs.nintendowifi.net
    dnsserv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dnsserv.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    dnsserv.bind(("0.0.0.0",53))
    while True:
        r = dnsserv.recvfrom(512)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 53))
        me = "".join(chr(int(x)) for x in s.getsockname()[0].split("."))
        s.send(r[0])
        rr = s.recv(512)
        if "gamestats2" in rr:
            rr = rr[:-4]+me
        dnsserv.sendto(rr, r[1])

def data_from_rowid(rowid):
    c = CONN.execute("select * from pokemon where rowid=?", (rowid,))
    data = c.fetchone()
    sourcepid = data[0]
    data = dict(zip(SQL_POKEMON_FIELDS, data[1:-1]))
    c.close()
    return (sourcepid, data)

def pokemon_html(rowid):
    sourcepid, data = data_from_rowid(rowid)
    data['pictureurlpart'] = "Shiny/BW" if data['shiny'] else "blackwhite/pokemon"
    data['specieszeroes'] = ("000" + str(data['species']))[-3:]
    data['speciestext'] = namemaps.species[data['species']]
    data['gendertext'] = {0:"Male",1:"Female", 2:"Genderless", 3:"???"}[data['gender']]
    data['itemtext'] = namemaps.items[data['item']] if data['item'] else " -- "
    data['pokerustext'] = "Pokerus" if data['pokerus'] else ""
    data['fatefultext'] = "Fateful" if data['fateful'] else ""
    data['attack1text'] = namemaps.attacks.get(data['attack1'], " -- ")
    data['attack2text'] = namemaps.attacks.get(data['attack2'], " -- ")
    data['attack3text'] = namemaps.attacks.get(data['attack3'], " -- ")
    data['attack4text'] = namemaps.attacks.get(data['attack4'], " -- ")
    data['abilitytext'] = namemaps.ability[data['ability']]
    data['naturetext'] = namemaps.nature[data['nature']]
    data['rowid'] = rowid

    html = """        <table>
            <tr>
                <td rowspan=4>
                    <table border=2>
                        <tr>
                            <td rowspan=4><img src="http://www.serebii.net/%(pictureurlpart)s/%(specieszeroes)s.png"</td>
                            <td width=150>#%(specieszeroes)s %(speciestext)s</td>
                            <td width=150>"%(nickname)s"</td>
                            <td width=150>Lvl %(level)s</td>
                            <td width=150>%(gendertext)s</td>
                        </tr>
                        <tr>
                            <td>%(abilitytext)s</td>
                            <td>%(naturetext)s</td>
                            <td>%(itemtext)s</td>
                            <td>%(fatefultext)s</td>
                        </tr>
                        <tr>
                            <td>OT %(otid)s</td>
                            <td>%(otname)s</td>
                            <td>%(pokerustext)s</td>
                            <td></td>
                        </tr>
                        <tr>
                            <td>%(attack1text)s</td>
                            <td>%(attack2text)s</td>
                            <td>%(attack3text)s</td>
                            <td>%(attack4text)s</td>
                        </tr>
                    </table>
                </td>
                <td>
                    <a href="/gtsplus/enqueue?rowid=%(rowid)s">Enqueue</a>
                </td>
            </tr>
            <tr>
                <td>
                    <a href="/gtsplus/delete?rowid=%(rowid)s">Delete</a>
                </td>
            </tr>
            <tr>
                <td>
                    <a href="/gtsplus/download?rowid=%(rowid)s">Download</a>
                </td>
            </tr>
        </table>""" % data
    return html

class GTSRequestHandler(BaseHTTPRequestHandler):
    server_version = "Microsoft-IIS/6.0"
    def do_GET(self):
        if self.path.startswith("/syachi2ds/web/"):
            self.gts_do_GET()
        elif self.path.startswith("/gtsplus/"):
            self.web_do_GET()
        else:
            self.send_error(404)

    def web_do_GET(self):
        global SEND_QUEUE
        print SEND_QUEUE
        try:
            path, query = self.path.split("?", 1)
        except ValueError:
            path = self.path
            query = ""
        path = path.split("/")[2:]
        if query:
            query = [ q.split("=",1) for q in query.split("&") ]
            querydata = dict(query)
        else:
            query = []
            querydata = dict()

        if path[0] == "list":
            avail = CONN.execute("select rowid from pokemon")
            htmls = map(lambda r: pokemon_html(r[0]), avail.fetchall())
            avail.close()
            available_pokemon = "".join(["<tr>%s</tr>\n"%x for x in htmls])
            fmt_rows = lambda rowdata: "\n".join(
                    ["<tr><td><a href='/gtsplus/enqueue?rowid=%s'>Add</a></td>%s</tr>"%
                        (row[0], "".join(["<td>%s</td>"%s for s in row[1:]]))
                    for row in rowdata])
            queued = []
            for rid in SEND_QUEUE:
                c = CONN.execute("select rowid, species, level, nickname, sourcepid from pokemon where rowid=?", (rid,))
                queued.append(c.fetchone())
                c.close()
            page = """<html><body>
                <h2>Available Pokemon:</h2>
                <table>%s</table>
                <h2>Send queue:</h2>
                <table>%s</table>
                </body></html>""" % (available_pokemon, fmt_rows(queued))
            self.send_response(200)
            self.send_header("Cache-control", "private")
            self.end_headers()
            self.wfile.write(page)
        elif path[0] == "enqueue":
            try:
                rowid = querydata['rowid']
            except KeyError:
                send_error(500)
                return
            c = CONN.execute("select nickname from pokemon where rowid=?", (rowid,))
            pkmn = c.fetchall()
            c.close()
            if len(pkmn) == 0:
                self.send_error(500)
            else:
                SEND_QUEUE.append(rowid)
                self.send_response(200)
                self.send_header("Cache-control", "private")
                self.end_headers()
                self.wfile.write("<html><head><meta http-equiv='refresh' content='1;url=/gtsplus/list/'><body>Added %s to the send queue. Redirecting back to the list...</body></html>"%pkmn[0])
        elif path[0] == "delete":
            try:
                rowid = querydata['rowid']
            except KeyError:
                send_error(500)
                return
            self.send_response(200)
            self.end_headers()
            if querydata.has_key('confirm'):
                c = CONN.execute("delete from pokemon where rowid=?", (rowid,)).close()
                CONN.commit()
                self.wfile.write("<html><head><meta http-equiv='refresh' content='1;url=/gtsplus/list/'><body>Deleted. Redirecting back to the list...</body></html>")
            else:
                self.wfile.write("""<html><body>Really delete? <a href="/gtsplus/delete?rowid=%s&confirm=1">Yes</a> <a href="/gtsplus/list">No</a></body></html>"""%(rowid,))
        elif path[0] == "download":
            try:
                rowid = querydata['rowid']
            except KeyError:
                send_error(500)
                return
            c = CONN.execute("select nickname,pkm_struct from pokemon where rowid=?", (rowid,))
            pkmn = c.fetchall()
            c.close()
            if len(pkmn) == 0:
                self.send_error(500)
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/x-pkm")
                self.send_header("Content-Disposition", "inline; filename=\"%s.pkm\""%pkmn[0][0])
                self.end_headers()
                self.wfile.write(pkmn[0][1])
        elif path[0] == "uploadtemp":
            path = querydata['path']
            pkm = open(path, 'r').read()
            add_pokemon(pkm, 0)
            self.send_response(200)
            self.end_headers()
            self.wfile.write("Success!")



    def gts_do_GET(self):
        path, query = self.path.split("?", 1)
        path = path.split("/")[3:]
        query = [ q.split("=",1) for q in query.split("&") ]
        querydata = dict(query)
        print path
        print query

        if len(query) == 1: # only pid= was set, so we havent been asked to do anything
            self.send(GTS_TOKEN)
        elif path[0] == 'common':
            if path[1] == 'setProfile.asp':
                self.send_encoded('\x00' * 8)
            else:
                print "UNKNOWN REQUEST:", path, query
                self.send_error(404)
        elif path[0] == 'worldexchange':
            if path[1] == 'info.asp':
                self.send_encoded('\x01\x00')
            elif path[1] == 'result.asp':
                global SEND_QUEUE
                if len(SEND_QUEUE) == 0:
                    self.send_encoded('\x05\x00')
                else:
                    rowid = SEND_QUEUE.pop()
                    c = CONN.execute("select pkm_struct from pokemon where rowid=?", (rowid,))
                    pkm = c.fetchone()[0]
                    c.close()
                    self.send_encoded(pkmtogts(pkm))
            elif path[1] == 'delete.asp':
                self.send_encoded('\x01\x00')
            #elif path[1] == 'search.asp':
            #    self.send_encoded('\x01\x00')
            elif path[1] == 'post.asp':
                data = querydata['data']
                bytes = urlsafe_b64decode(data)
                pkm = pkmlib.decode(bytes[12:232])
                add_pokemon(pkm, querydata['pid'])
                self.send_encoded('\x0c\x00') # reject it, kicking the pokemon back to the client
            else:
                print "UNKNOWN REQUEST:", path, query
                self.send_error(404)
        else:
            self.send_error(404)
            self.wfile.close()

    def hash(self, data):
        m = hashlib.sha1()
        m.update(GTS_SALT + urlsafe_b64encode(data) + GTS_SALT)
        return data + m.hexdigest()

    def send_encoded(self, body):
        self.send(self.hash(body))

    def send(self, body):
        segments = ["HTTP/1.1 200 OK"]
        # TODO: use a proper date formatter
        months=["???", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul",
            "Aug", "Sep", "Oct", "Nov", "Dec"]
        days=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        t=time.gmtime()
        segments += ["Date: %s, %02i %s %i %02i:%02i:%02i GMT"%(days[t[6]],
                     t[2], months[t[1]], t[0], t[3], t[4], t[5]) ]
        for key,value in STD_SERV_HEADERS:
            segments += [key + ": " + value]
        header = "\r\n".join(segments) + "\r\n\r\n"
        print header + body
        self.wfile.write(header + body)

CONN = open_db("gtsplus.sqlite")
thread.start_new_thread(dnsspoof,())
httpd = HTTPServer(('', 80), GTSRequestHandler)
httpd.serve_forever()
