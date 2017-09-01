proj4.defs('EPSG:4326', "+proj=longlat +ellps=WGS84 +datum=WGS84 +units=degrees");

var resolutions = [];
var extent = 180.0;
var tile_size = 512;
var resolutions = Array(17).fill().map((_, i) => ( extent / tile_size / Math.pow(2, i) ));

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

function createStatsStyle() {
        var fill = new ol.style.Fill({color: '#000000'});
        var stroke = new ol.style.Stroke({color: '#000000', width: 1});
        var text = new ol.style.Text({
                text: 'XYXYXY',
		fill: fill,
		stroke: stroke,
		font: '16px "Open Sans", "Arial Unicode MS"'
        });


	var styles = [];
	return function(feature, resolution) {
		var length = 0;
		//console.log(feature);
		text.setText('Occurrences: '+feature.get('total'));
		console.log(feature.get('total'));
		styles[length++] = new ol.style.Style({
			stroke: new ol.style.Stroke({color: '#000000'}),
			text: text
		});
		styles.length = length;
		return styles;
	};
}

var tileGrid = new ol.tilegrid.TileGrid({
    extent: ol.proj.get('EPSG:4326').getExtent(),
    minZoom: 0,
    maxZoom: 16,
    resolutions: resolutions,
    tileSize: 512,
});

layers['EPSG:4326'] = new ol.layer.VectorTile({
    source: new ol.source.VectorTile({
	projection: 'EPSG:4326',
	format: new ol.format.MVT(),
	tileGrid: tileGrid,
	tilePixelRatio: 8,
	url: 'http://mb.gbif.org:8080/tiles/{z}_{x}_{y}.pbf',
        wrapX: false
    }),
    style: createStyle(),
});

layers['Grid'] = new ol.layer.Tile({
	extent: ol.proj.get('EPSG:4326').getExtent(),
	source: new ol.source.TileDebug({
		projection: 'EPSG:4326',
		tileGrid: tileGrid,
		wrapX: false
	}),
});

var map = new ol.Map({
    layers: [
	layers['EPSG:4326'],
	layers['Grid']
    ],
    target: 'map',
    view: new ol.View({
	center: [10.7522, 59.9139],
	projection: 'EPSG:4326',
	zoom: 10
    }),
});
