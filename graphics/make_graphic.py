from cps_migration.settings import BASE_DIR
import fiona, geojson
import subprocess, os
from mapbox import Static 
from tcr_tools.geocode import get_lat_lon
from transfers.models import School

### START CONFIG ###
shapes_dir = BASE_DIR + '/graphics/shapes/'
elem_shapes_path = shapes_dir + '/elsd'
sec_shapes_path = shapes_dir + '/scsd'
uni_shapes_path = shapes_dir + '/unsd'
shapes_paths = [elem_shapes_path,sec_shapes_path,uni_shapes_path]
# ugh ... so suburban schools use boundaries, which are named in shapefiles
# and cps schools use points, which are derived from address in data
map_data = {
            'thorton':
                      {
                       'sub_dists': ['Thornton Township High School District 205'],#['Thornton Twp HSD 205'],
                       'cps_schools': ['Chicago Vocational Career Acad HS','Morgan Park High School'],
                       'zoom': 1,
                      },
            'rockford':
                      {
                       'sub_dists': ['Rockford School District 205'],
                       'cps_schools': ['Bradwell Comm Arts & Sci Elem Sch'],
                       'zoom': 1,
                      }

           }
maps_dir = BASE_DIR + '/graphics/maps/'
simplification_level = "0.005"
map_img = 'mapbox.streets'
### END CONFIG ###

service = Static()


def make_all_maps():
    for map_datum in map_data:
        make_a_map(map_datum)


def make_a_map(map_datum):
    print map_datum
    features = []
    for sub_dist_name in map_data[map_datum]['sub_dists']:
        feature = get_boundary_feature(sub_dist_name)
        features.append(feature)
    for cps_school_name in map_data[map_datum]['cps_schools']:
        feature = get_point_feature(cps_school_name)
        features.append(feature)
    response = service.image(map_img,features=features,z=map_data[map_datum]['zoom'])
    map_file_path = maps_dir + map_datum + '.png'
    with open(map_file_path,'wb') as output:
        output.write(response.content)
    print map_file_path


def get_boundary_feature(dist_name):
    dist_feature = get_dist_boundary_by_name(boundary_collection(),dist_name)
    opt_feature = optimize_boundary(dist_feature)
    return opt_feature


def get_point_feature(school_name):
    try:
        school = School.objects.get(name=school_name)
    except Exception, e:
        import ipdb; ipdb.set_trace()
    lat, lon = get_lat_lon(address=school.address,city=school.city,zip=school.zip_code)
    feature = {'type':'Feature','properties':{'marker-size':'small','marker-color':'#00F'},'geometry':{'type':'Point','coordinates':[float(lon),float(lat)]}}
    return feature

def boundary_collection():
    boundary_files = [fiona.open(x) for x in shapes_paths]
    collection = []
    for boundary_file in boundary_files:
        for boundary_feature in boundary_file.items():
            collection.append(boundary_feature[1])
    return collection


def optimize_boundary(dist_feature):
    dist_name = dist_feature['properties']['NAME'].replace(' ','-')
    dist_file_path = shapes_dir + dist_name + '.geojson'
    simp_file_path = shapes_dir + 'simp_' + dist_name + '.geojson'
    dist_file = open(dist_file_path,'w')
    geojson.dump(dist_feature,dist_file)
    dist_file.close()
    if os.path.isfile(simp_file_path):
        os.remove(simp_file_path)
    subprocess.call(
                    [
                     "ogr2ogr",
                     "-f","GeoJSON",
                     "-simplify", simplification_level,
                     simp_file_path, # output file
                     dist_file_path  # input file
                    ]
                   )
    return geojson.load(open(simp_file_path))


def get_boundary_file_by_type(type):
    # deprecated
    return
    if type == 'elem':
        return fiona.open(elem_shapes_path)
    elif type == 'sec':
        return fiona.open(sec_shapes_path)
    elif type == 'uni':
        return fiona.open(uni_shapes_path)


def get_dist_boundary_by_name(boundary_collection,dist_name):
    try:
        return [x for x in boundary_collection if x['properties']['NAME'] == dist_name][0]
    except Exception, e:
        import ipdb; ipdb.set_trace()


def get_dist_boundaries_by_no_and_keywords(number=None,keyword=None):
    results = {}
    results['number_matches'] = [x for x in boundary_collection() if x['properties']['NAME'].split(' ')[-1] == str(number)]
    results['keyword_matches'] = [x for x in boundary_collection() if keyword.lower() in [y.lower() for y in x['properties']['NAME'].split(' ')]]
    results['both_matches'] = [x for x in results['number_matches'] if x in results['keyword_matches']]
    return results
