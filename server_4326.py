import tornado.ioloop
import tornado.web
import tornado.httpserver
import io
import os

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import mercantile
import pyproj
import yaml
import sys
import itertools

def GetTM2Source(file):
    with open(file,'r') as stream:
        tm2source = yaml.load(stream)
    return tm2source

buffer_sizes = []

def GeneratePrepared(layers):
    queries = []
    for layer in layers['Layer']:
        buffer_size = str(layer['properties']['buffer-size']*2)
        if (buffer_size not in buffer_sizes):
            buffer_sizes.append(buffer_size)
        layer_query = layer['Datasource']['table'].lstrip().rstrip()	# Remove lead and trailing whitespace
        layer_query = layer_query[1:len(layer_query)-6]			# Remove enough characters to remove first and last () and "AS t"
        layer_query = layer_query.replace("geometry", "ST_AsMVTGeom(geometry,!bbox_nobuffer!,4096,"+buffer_size+",true) AS mvtgeometry")
        layer_query = layer_query.replace("!bbox!", "!bbox_"+buffer_size+"_buffer!")
        base_query = "SELECT ST_ASMVT('"+layer['id']+"', 4096, 'mvtgeometry', tile) FROM ("+layer_query+" WHERE ST_AsMVTGeom(geometry,!bbox_nobuffer!,4096,"+buffer_size+",true) IS NOT NULL) AS tile"
        queries.append(base_query.replace("!bbox_nobuffer!","$1").replace("!scale_denominator!","$2").replace("!pixel_width!","$3").replace("!pixel_height!","$4").replace("!bbox_"+buffer_size+"_buffer!", "$"+str(buffer_sizes.index(buffer_size)+5)))

    chunk = ""
    for buffer_size in buffer_sizes:
        chunk = chunk + ", geometry"

    prepared = "PREPARE gettile(geometry, numeric, numeric, numeric"+chunk+") AS "
    prepared = prepared + " UNION ALL ".join(queries) + ";"
    print(prepared)
    return(prepared)

print("Starting up")
layers = GetTM2Source("/mapping/data.yml")
prepared = GeneratePrepared(layers)
connection_string = 'postgresql://'+os.getenv('POSTGRES_USER','openmaptiles')+':'+os.getenv('POSTGRES_PASSWORD','openmaptiles')+'@'+os.getenv('POSTGRES_HOST','postgres')+':'+os.getenv('POSTGRES_PORT','5432')+'/'+os.getenv('POSTGRES_DB','openmaptiles')
engine = create_engine(connection_string)
inspector = inspect(engine)
DBSession = sessionmaker(bind=engine)
session = DBSession()
print("Running prepare statement")
session.execute(prepared)

def bounds(zoom,x,y,buff):
    #inProj = pyproj.Proj(init='epsg:3575')
    #outProj = pyproj.Proj(init='epsg:3575')
    #lnglatbbox = mercantile.bounds(x,y,zoom)
    #ws = (pyproj.transform(inProj,outProj,lnglatbbox[0],lnglatbbox[1]))
    #en = (pyproj.transform(inProj,outProj,lnglatbbox[2],lnglatbbox[3]))

    #map_width_in_metres = 2 * 2**0.5*6371007.2
    map_width_in_metres = 180.0
    #tile_width_in_pixels = 512.0
    #standardized_pixel_size = 0.00028
    #map_width_in_pixels = tile_width_in_pixels*(2.0**zoom)

    tiles_down = 2**(zoom)
    tiles_across = 2**(zoom)

    #arc x = x - 2**(zoom-1)
    #arctic y = -(y - 2**(zoom-1)) - 1
    x = x - 2**(zoom)
    y = -(y - 2**(zoom)) - 1 - 2**(zoom-1)

    #print(x, y);

    tile_width_in_metres = (map_width_in_metres / tiles_across)
    tile_height_in_metres = (map_width_in_metres / tiles_down)
    ws = ((x - buff)*tile_width_in_metres,  (y - buff)*tile_width_in_metres)
    en = ((x+1+buff)*tile_height_in_metres, (y+1+buff)*tile_height_in_metres)

    #print("Zoom, buffer", zoom, buff)
    #print("West:  ", ws[0])
    #print("South: ", ws[1])
    #print("East:  ", en[0])
    #print("North: ", en[1])

    return {'w':ws[0],'s':ws[1],'e':en[0],'n':en[1]}

def zoom_to_scale_denom(zoom):						# For !scale_denominator!
    # From https://github.com/openstreetmap/mapnik-stylesheets/blob/master/zoom-to-scale.txt
    #map_width_in_metres = 2 * 2**0.5*6371007.2 # Arctic
    #map_width_in_metres = 180.0
    map_width_in_metres = 40075016.68557849
    tile_width_in_pixels = 512.0 # This asks for a zoom level higher, since the tiles are doubled.
    standardized_pixel_size = 0.00028
    map_width_in_pixels = tile_width_in_pixels*(2.0**zoom)
    return str(map_width_in_metres/(map_width_in_pixels * standardized_pixel_size))

def replace_tokens(query,tilebounds,buffered_tilebounds,scale_denom,z):
    s,w,n,e = str(tilebounds['s']),str(tilebounds['w']),str(tilebounds['n']),str(tilebounds['e'])

    start = query.replace("!bbox!","ST_SetSRID(ST_MakeBox2D(ST_Point("+w+", "+s+"), ST_Point("+e+", "+n+")), 4326)").replace("!scale_denominator!",scale_denom).replace("!pixel_width!","512").replace("!pixel_height!","512")

    for buffer_size in buffer_sizes:
        token = "!bbox_"+buffer_size+"_buffer!"
        idx = buffer_sizes.index(buffer_size)

        t = buffered_tilebounds[idx]
        s,w,n,e = str(t['s']),str(t['w']),str(t['n']),str(t['e'])
        start = start.replace(token,"ST_SetSRID(ST_MakeBox2D(ST_Point("+w+", "+s+"), ST_Point("+e+", "+n+")), 4326)")

    return start

def get_mvt(zoom,x,y):
    try:								# Sanitize the inputs
        sani_zoom,sani_x,sani_y = float(zoom),float(x),float(y)
        del zoom,x,y
    except:
        print('suspicious')
        return 1

    scale_denom = zoom_to_scale_denom(sani_zoom)
    tilebounds = bounds(sani_zoom,sani_x,sani_y,0)

    buffered_tilebounds = []
    chunk = ""
    for buffer_size in buffer_sizes:
        t = bounds(sani_zoom,sani_x,sani_y,int(buffer_size)/512.0)
        buffered_tilebounds.append(t)

        chunk = chunk + ", !bbox_"+buffer_size+"_buffer!"

    final_query = "EXECUTE gettile(!bbox!, !scale_denominator!, !pixel_width!, !pixel_height!"+chunk+");"
    sent_query = replace_tokens(final_query,tilebounds,buffered_tilebounds,scale_denom,sani_zoom)
    print(sani_zoom, sani_x, sani_y, sent_query)
    response = list(session.execute(sent_query))
    layers = filter(None,list(itertools.chain.from_iterable(response)))
    final_tile = b''
    for layer in layers:
        final_tile = final_tile + io.BytesIO(layer).getvalue()
    return final_tile

class GetTile(tornado.web.RequestHandler):

    def get(self, zoom,x,y):
        self.set_header("Content-Type", "application/x-protobuf")
        self.set_header("Content-Disposition", "attachment")
        self.set_header("Access-Control-Allow-Origin", "*")
        response = get_mvt(zoom,x,y)
        self.write(response)

def m():
    if __name__ == "__main__":
        # Make this prepared statement from the tm2source
        application = tornado.web.Application([
            (r"/tiles/([0-9]+)[/_]([0-9]+)[/_]([0-9]+).pbf", GetTile),
            (r"/([^/]*)", tornado.web.StaticFileHandler, {"path": "./static", "default_filename": "index.html"})
        ])

        server = tornado.httpserver.HTTPServer(application)
        server.bind(8080)
        server.start(1)
        print("Postserve started..")
        #application.listen(8080)

        tornado.ioloop.IOLoop.instance().start()

m()
