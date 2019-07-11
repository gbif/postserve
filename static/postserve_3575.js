proj4.defs("EPSG:3575", "+proj=laea +lat_0=90 +lon_0=10 +x_0=0 +y_0=0 +ellps=WGS84 +datum=WGS84 +units=m +no_defs");

var halfWidth = Math.sqrt(2) * 6371007.2;
var extent = [-halfWidth, -halfWidth, halfWidth, halfWidth];
ol.proj.get("EPSG:3575").setExtent(extent);

var tile_size = 512;
var max_zoom = 16;
var resolutions = Array.from(new Array(max_zoom), (x,i) => (halfWidth/(tile_size*Math.pow(2,i-1))));

var layers = [];

densityColours = ["#FFFF00", "#FFCC00", "#FF9900", "#FF6600", "#FF3300", "#FF0000"];

function createDensityStyle2() {
	var point = new ol.style.Style({
		image: new ol.style.Circle({
			fill: new ol.style.Fill({color: '#FF0000'}),
			radius: 1
		}),
		fill: new ol.style.Fill({color: '#FF0000'})
	});

	var styles = [];
	return function(feature, resolution) {
		var length = 0;
		//console.log(feature);
		var magnitude = Math.trunc(Math.min(5, Math.floor(Math.log(feature.get('total'))))) - 1;
		//console.log("Colour ", magnitude, densityColours[magnitude]);
		//styles[length++] = point;
		styles[length++] = new ol.style.Style({
			image: new ol.style.Circle({
				fill: new ol.style.Fill({color: densityColours[magnitude]}),
				radius: 1
			}),
			fill: new ol.style.Fill({color: densityColours[magnitude]})
		});
		styles.length = length;
		return styles;
	};
}

var tile_grid = new ol.tilegrid.TileGrid({
	extent: ol.proj.get('EPSG:3575').getExtent(),
	origin: [-halfWidth,halfWidth],
	minZoom: 0,
	maxZoom: max_zoom,
	resolutions: resolutions,
	tileSize: tile_size,
});

layers['EPSG:3575'] = new ol.layer.VectorTile({
	title: 'EPSG:3575 (Default size)',
	type: 'base',
	source: new ol.source.VectorTile({
		projection: 'EPSG:3575',
		format: new ol.format.MVT(),
		tileGrid: tile_grid,
		tilePixelRatio: 8,
		url: '/tiles/{z}_{x}_{y}.pbf',
		wrapX: false
	}),
	style: createStyle(),
});

layers['Grid'] = new ol.layer.Tile({
	title: 'Tile grid',
        type: 'Grid',
	extent: ol.proj.get('EPSG:3575').getExtent(),
	source: new ol.source.TileDebug({
		projection: 'EPSG:3575',
		tileGrid: tile_grid,
		wrapX: false
	}),
});

// Show the tiles are 1:1 scale; cover 4096 screen pixels with the 4096px vector tiles.
var overzoom_tile_size = 4096;
var overzoom_resolutions = Array.from(new Array(max_zoom-3), (x,i) => (halfWidth/(overzoom_tile_size*Math.pow(2,i-1))));
var overzoom_tile_grid = new ol.tilegrid.TileGrid({
	extent: ol.proj.get('EPSG:3575').getExtent(),
	origin: [-halfWidth,halfWidth],
	minZoom: 0,
	maxZoom: max_zoom,
	resolutions: overzoom_resolutions,
	tileSize: overzoom_tile_size,
});
layers['OZ_EPSG:3575'] = new ol.layer.VectorTile({
	title: 'Real size',
	type: 'base',
	source: new ol.source.VectorTile({
		projection: 'EPSG:3575',
		format: new ol.format.MVT(),
		tileGrid: overzoom_tile_grid,
		tilePixelRatio: 1,
		url: '/tiles/{z}_{x}_{y}.pbf',
		wrapX: false
	}),
	style: createStyle(),
});

var map = new ol.Map({
	layers: [
		layers['Grid'],
		new ol.layer.Group({
			title: 'Tiles',
			layers: [
				layers['OZ_EPSG:3575'],
				layers['EPSG:3575'],
			]
		})
	],
	target: 'map',
	view: new ol.View({
		center: [0, 0],
		projection: 'EPSG:3575',
		zoom: 2
	}),
});

var layerSwitcher = new ol.control.LayerSwitcher();
map.addControl(layerSwitcher);
