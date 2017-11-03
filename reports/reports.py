from cps_migration.settings import BASE_DIR
from transfers.models import School, Student, Transfer
from geos.models import CommArea
import csv
from tcr_tools.typify import intify, floatify

### START CONFIG ###
output_dir = BASE_DIR + '/reports/output/'
### END CONFIG ###

years = sorted(list(set([x.school_year for x in Transfer.objects.all()])))

def get_transfers():
    """
    return all transfers with complete to/from home/serving info
    """
    return Transfer.objects.filter(from_home_school__isnull=False).\
            filter(from_serving_school__isnull=False).\
            filter(to_home_school__isnull=False).\
            filter(to_serving_school__isnull=False)


def get_cps_transfers():
    """
    return all *complete* cps transfers out
    """
    return [x for x in get_transfers() if x.from_home_school.cps_id]


def get_cps_schools():
    """
    return schools with a cps id
    or the specially identified charters
    that were missing an id
    """
    return [x for x in School.objects.all() if x.cps_id] + \
            [x for x in School.objects.all() if x.name in \
		['Perspectives Charter High School',
		 'North Lawndale Charter HS',
		 'Noble Street Charter Schools',
		 'Aspira Charter Schools',
		 'Prologue - Johnston Fine Arts HS',
		 'Chicago International Charter',
		 'Univ of Chicago Charter Schools',
		 'UNO Academy Charter Schools',
		 'LEARN Charter Schools',
		 'Galapagos Elem Charter School',
		 'KIPP Chicago Charter Schools',
		 'Youth Connections Charter HS']
	    ]


def get_charters():
    return [x for x in get_cps_schools() if x.rcdts[-1].lower() == 'c']


def get_charter_transfers():
    charters = get_charters()
    return [x for x in get_transfers() if x.from_serving_school in charters]


def get_maj_race_schools(race='black',threshold=0.8):
    try:
        return [x for x in get_cps_schools() if x.male and getattr(x,race)/float(x.male+x.female) >= threshold] 
    except:
        import ipdb; ipdb.set_trace()

def get_district(rcdts):
    return rcdts[5:9]

def comms_to_burbs():
    """
    what were the largest migration patterns (school to school; Chicago community area to suburb name)
    """
    comm_to_burb_transfers = {}
    print('getting transfers')
    transfers = get_transfers()
    print('len(transfers)',len(transfers))
    print('compiling transfers by comm, burb')
    for t in transfers:
        comm = t.from_home_school.comm_area_name
        # just cps ... could replace this with cps_transfers
        if comm:
            burb = t.to_home_school.city
            slug = comm.lower().strip() + '_' + burb.lower().strip()
            if slug not in comm_to_burb_transfers:
                comm_to_burb_transfers[slug] = {}
                comm_to_burb_transfers[slug]['comm'] = comm
                comm_to_burb_transfers[slug]['burb'] = burb
                comm_to_burb_transfers[slug]['count'] = 0
            comm_to_burb_transfers[slug]['count'] += 1
    print('len(comm_to_burb_transfers)',len(comm_to_burb_transfers.keys()))
    print('sorting transfers')
    sorted_transfers = sorted([(comm_to_burb_transfers[x]['comm'],comm_to_burb_transfers[x]['burb'],comm_to_burb_transfers[x]['count']) for x in comm_to_burb_transfers], \
                key = lambda x: x[2], reverse=True)
    print('len(sorted_transfers)',len(sorted_transfers))

    # output
    outfile_path = output_dir + 'comms_to_burbs.csv'
    outfile = open(outfile_path,'w')
    out_headers = ['comm_area','city','count']
    outcsv = csv.DictWriter(outfile,out_headers)
    outcsv.writeheader()
    for row in sorted_transfers:
        outcsv.writerow({'comm_area':row[0],'city':row[1],'count':row[2]})
    outfile.close()
    return sorted_transfers


def transfers_by_comm_area_by_year(connect=True):
    """
    list annual transfer counts by community area.
    if connect = True, only count connecting transfers
    """
    # set up data
    data = dict()

    # set up output file
    outfile_name = output_dir + 'transfers_by_commarea_by_year.csv'
    if connect:
        outfile_name = output_dir + 'connecting_transfers_by_commarea_by_year.csv'
    outfile = open(outfile_name,'w')
    out_headers = ['Comm Area','pct_black','pct_latino','pct_white','pct_poverty','pct_under_18']
    out_headers +=  sorted(list(years))
    out_csv = csv.DictWriter(outfile, out_headers)
    out_csv.writeheader()
    
    for comm_area in CommArea.objects.all():
        # for each comm area ...
        data[comm_area.name] = dict()
        ca_schools = comm_area.school_set.all()
        for ca_school in ca_schools:
            if ca_school.rcdts[-1].lower() == 'c' or ca_school.attendance_type != 'Attendance Area School':
                print('excluding',ca_school.from_home_school.__dict__)
                continue
            print('including',ca_school.from_home_school.__dict__)
            # ... get each school and its transfers ...
            if connect:
                school_transfers = Transfer.objects.filter(from_home_school=ca_school,to_serving_school__isnull=False)
            else:
                school_transfers = Transfer.objects.filter(from_home_school=ca_school)
            for year in years:
                # add year to ca data only if it doesn't exist
                if year not in data[comm_area.name].keys():
                    data[comm_area.name][year] = 0
                # ... else, add to that year's totals
                this_years_transfers = [x for x in school_transfers if x.school_year == year]
                data[comm_area.name][year] += len(this_years_transfers)
        # write results to file
        try:
            row = {
                    'Comm Area': comm_area.name,
                    'pct_black': round(comm_area.pct_black,2),
                    'pct_latino': round(comm_area.pct_latino,2),
                    'pct_white': round(comm_area.pct_white,2),
                    'pct_poverty': round(comm_area.pct_poor,2),
                    'pct_under_18': round(sum([intify(getattr(comm_area,x)) for x in ['age_under_5','age_5_to_9','age_10_to_14','age_15_to_17']])/floatify(comm_area.total_pop),2)
                  }
        except Exception, e:
            import ipdb; ipdb.set_trace()
        for year in years:
            row[year] = data[comm_area.name][year] if year in data[comm_area.name].keys() else 0
        out_csv.writerow(row)
    outfile.close()
    return data


def transfers_by_comm_area_with_minor_pop():
    """
    *Which community areas have seen the highest rates of out-of-district transfers 
    from neighborhood schools (adjusted for size of 0-18 population)? 
    Are they majority black?
    headers = [community area, pct_black, poverty_rate, transfer count, under 18 pop, rate transfers/kids]
    """
    # data
    data = dict()
    for comm_area in CommArea.objects.all():
        data[comm_area.name] = dict()
        data[comm_area.name]['transfer_count'] = 0
        ca_schools = comm_area.school_set.all()
        for ca_school in ca_schools:
            if ca_school.rcdts[-1].lower() == 'c' or ca_school.attendance_type != 'Attendance Area School':
                print('excluding',ca_school.from_home_school.__dict__)
                continue
            print('including',ca_school.from_home_school.__dict__)
            ca_transfers = Transfer.objects.filter(from_home_school=ca_school)
            data[comm_area.name]['transfer_count'] += len(ca_transfers)
        under_18_pop = sum([intify(getattr(comm_area,x)) for x in ['age_under_5','age_5_to_9','age_10_to_14','age_15_to_17']])
        data[comm_area.name]['comm_area'] = comm_area.name
        data[comm_area.name]['pct_black'] = comm_area.pct_black
        data[comm_area.name]['pct_latino'] = comm_area.pct_latino
        data[comm_area.name]['pct_white'] = comm_area.pct_white
        data[comm_area.name]['poverty_rate'] = comm_area.pct_poor
        data[comm_area.name]['under_18_pop'] = under_18_pop
        data[comm_area.name]['transfer_rate'] = len(ca_transfers)/float(under_18_pop)

    # output 
    outfile_path = output_dir + 'transfers_by_comm_area_with_minor_pop.csv'
    outfile = open(outfile_path,'w')
    outheaders = ['comm_area', 'pct_black', 'pct_latino', 'pct_white', 'poverty_rate', 'transfer_count', 'under_18_pop','transfer_rate']
    outcsv = csv.DictWriter(outfile,outheaders)
    outcsv.writeheader()

    for comm_area in data:
        outcsv.writerow(data[comm_area])
    
    outfile.close()


def transfer_counts_by_dest(geo='city',charters=False):
    """
    Which cities/counties have taken in the highest number/percentage of out-of-district transfers from CPS?
    headers = [city, count]
    data = {'city': count}
    specify city or county in geo param
    specify charters or all in charters param
    """
    data = {}
    if charters:
        transfers = get_charter_transfers()
    else:
        transfers = get_cps_transfers()
    for transfer in transfers:
        if getattr(transfer.to_home_school,geo) not in data:
            data[getattr(transfer.to_home_school,geo)] = 0
        data[getattr(transfer.to_home_school,geo)] += 1
    data_list = sorted([(x,data[x]) for x in data], key = lambda z: z[1], reverse = True)
    outfile = open(output_dir + ('charter' if charters else 'cps') + '_transfer_counts_by_' + geo + '.csv','w')
    outcsv = csv.writer(outfile)
    outcsv.writerow([geo,'count'])
    for row in data_list:
        outcsv.writerow(row)
    outfile.close()
    

def side_report(sides,name):
    """
    Is there a clear pattern of where students are going by side? (say a county or number of cities?)
    see: https://en.wikipedia.org/wiki/Community_areas_in_Chicago#/media/File:Map_of_the_Community_Areas_and_%27Sides%27_of_the_City_of_Chicago.svg
    sides: list 
	options include:
	    West Side
	    Central
	    Northwest Side
	    South Side
	    Far Southwest Side
	    North Side
	    Far North Side
	    Southwest Side
	    Far Southeast Side
    name: string
        descriptive of sides	
    """
    data = {}
    cps_transfers = get_transfers()#get_cps_transfers()
    cas = CommArea.objects.filter(side__in=sides)
    side_transfers = [x for x in cps_transfers if x.from_home_school.comm_area in cas]
    for transfer in side_transfers:
        slug = transfer.to_home_school.city.lower().strip() + '_' + transfer.to_home_school.county.lower().strip()
        if slug not in data:
            data[slug] = {'city':transfer.to_home_school.city,'county':transfer.to_home_school.county,'transfer_count':0}
        data[slug]['transfer_count']+=1

    # output
    try:
        outfile_path = output_dir + name + '_side_report.csv'
        outfile = open(outfile_path,'w')
        outheaders = ['city','county','transfer_count']
        outcsv = csv.DictWriter(outfile,outheaders)
        outcsv.writeheader()
        for datum in data:
            row = {'city': data[datum]['city'],'county': data[datum]['county'], 'transfer_count': data[datum]['transfer_count']}
            outcsv.writerow(row)
        outfile.write('\r\n')
        msg = 'Note: this report defines the ' + name + ' as including the following: ' + ','.join(sides)
        msg += '\r\n'
        msg += 'Reference: https://en.wikipedia.org/wiki/Community_areas_in_Chicago#/media/File:Map_of_the_Community_Areas_and_%27Sides%27_of_the_City_of_Chicago.svg'
        outfile.write(msg)
        outfile.close()
    except Exception, e:
        import ipdb; ipdb.set_trace()


def transfer_counts_maj_race_schools(race='black',threshold=0.8):
    # output file
    outfile_path = output_dir + 'transfers_maj_' + race + '_schools.csv'
    outfile = open(outfile_path,'w')
    headers = ['school',race + '_students','total_students','pct_' + race] + sorted(list(years))
    outcsv = csv.DictWriter(outfile,headers)
    outcsv.writeheader()

    # query
    maj_race_schools = get_maj_race_schools(race=race,threshold=threshold)
    for school in maj_race_schools:
        row = {
               'school': school.name,
               race + '_students': getattr(school,race),
               'total_students': school.male + school.female,
               'pct_' + race: getattr(school,race)/float(school.male + school.female),
               }
        for year in years:
            row[year] = len(Transfer.objects.filter(from_serving_school=school,to_serving_school__isnull=False,school_year=year))
        outcsv.writerow(row)
    
    # writeout
    outfile.close()


def recv_schools_and_dists_by_cps_and_seg_school_transfers(race='black',threshold=0.8):
    # outfile
    outfile_path = output_dir + 'receiving_schools_and_districts_with_cps_transfer_counts.csv'
    outfile = open(outfile_path,'w')
    headers = ['school','district (RDCTS code)','city','county','CPS transfers','CPS transfers (maj ' + race + ' schools)']
    outcsv = csv.DictWriter(outfile,headers)
    outcsv.writeheader()
            
    # query
    school_counts = {}

    print('getting segregated schools')
    maj_race_schools = get_maj_race_schools(race=race,threshold=threshold)

    print('rolling thru transfers')
    for transfer in get_transfers():
        to_school = transfer.to_serving_school
        if not to_school:
            continue
        if to_school not in school_counts:
            school_counts[to_school] = {
                                     'school':to_school.name,
                                     'district (RDCTS code)': get_district(to_school.rcdts),
                                     'city': to_school.city,
                                     'county': to_school.county,
                                     'CPS transfers': 0,
                                     'CPS transfers (maj ' + race + ' schools)': 0,
                                    }
        school_counts[to_school]['CPS transfers'] += 1
        from_school = transfer.from_home_school
        if from_school and from_school in maj_race_schools:
            school_counts[to_school]['CPS transfers (maj ' + race + ' schools)'] += 1
    print('sorting')
    school_data = sorted([school_counts[school] for school in school_counts], key = lambda x: x['CPS transfers (maj ' + race + ' schools)'],reverse=True)
    print('writing')
        outcsv.writerow(row)

    outfile.close()



def transfer_out_dests(school):
    # outfile
    outfile_path = output_dir + school.replace(' ','-').replace('.','') + '_transfer_out_destinations.csv'
    outfile = open(outfile_path,'w')
    headers = ['school','district (RCDTS code)','city','county'] + years + ['total']
    outcsv = csv.DictWriter(outfile,headers)
    outcsv.writeheader()

    # query
    destinations = {} # key to_school_obj
    school = School.objects.get(name=school)
    transfers = Transfer.objects.filter(from_serving_school=school)
    for transfer in transfers:
        to_school = transfer.to_serving_school
        if not to_school:
            continue
        if to_school not in destinations:
            destinations[to_school] = {
                                       'school': to_school.name,
                                       'district (RCDTS code)': get_district(to_school.rcdts),
                                       'city': to_school.city,
                                       'county': to_school.county,
                                       'total': 0
                                      }
            for year in years:
                destinations[to_school][year] = 0
        destinations[to_school][transfer.school_year] += 1
        destinations[to_school]['total'] += 1
    destinations_data = sorted([destinations[x] for x in destinations], key = lambda z:z['total'], reverse=True)  

    # writeout
    for row in destinations_data:
        outcsv.writerow(row)

    outfile.close()



def charter_school_report():
    """
    Are charters seeing a higher rate of out-of-district transfers than traditional district schools?
    """
    # outfile
    outfile_path = output_dir + 'charters.csv'
    outfile = open(outfile_path,'w')
    headers = ['name','rcdts','cps_id','address','comm_area','pct_black'] + years + ['total']
    outcsv = csv.DictWriter(outfile,headers)
    outcsv.writeheader()

    # query
    for charter in get_charters(): # check query
        row = {
                'name': charter.name,
                'rcdts': charter.rcdts,
                'cps_id': charter.cps_id,
                'address': charter.address,
                'comm_area': charter.comm_area.name if charter.comm_area else None,
                'pct_black': round(charter.black/float(charter.male+charter.female),2)
            }
        for year in years:
            row[year] = len(Transfer.objects.filter(from_serving_school=charter,school_year=year,to_home_school__isnull=False,to_serving_school__isnull=False))
        row['total'] = sum(row[year] for year in years)
        
        # writeout
        outcsv.writerow(row)
    outfile.close()
    print outfile_path


def report_runner(): 
    print('comms_to_burbs()')
    comms_to_burbs()
    
    print('transfers_by_comm_area_by_year()')
    transfers_by_comm_area_by_year()

    print('transfers_by_comm_area_with_minor_pop()')
    transfers_by_comm_area_with_minor_pop()
    
    print('cps_transfer_counts_by_city()')
    cps_transfer_counts_by_city()

    print('cps_transfer_counts_by_county()')
    cps_transfer_counts_by_county()

    for side in ['West Side','South Side','Far Southeast Side']:
        print('side_report(',side,')')
        side_report(side,side.replace(' ','_'))

    print('transfer_counts_maj_race_schools()')
    transfer_counts_maj_race_schools()

    print('recv_schools_and_dists_by_cps_and_seg_school_transfers()')
    recv_schools_and_dists_by_cps_and_seg_school_transfers()
    
    print('transfer_out_dests("Depriest Elem School")')
    transfer_out_dests('Depriest Elem School')


