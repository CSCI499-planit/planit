"""
    data cleaning pipeline
"""
import os
import random
from dotenv import load_dotenv
import pandas as pd
import requests

# data extraction
load_dotenv()
API_KEY = os.getenv('GEOAPIFY_API_KEY')
URL = f'https://api.geoapify.com/v2/places?api_key={API_KEY}'

def extract_geoapify(url:str, params:str = '') -> pd.DataFrame:
    """
        extract data from geoapify API payload & return as dataframe
        params example: categories=healthcare&limit=100
    """
    try:
        res = requests.get(url=f'{url}&{params}',timeout=30)
        data = res.json()
        geoapify_places = pd.read_json(data)
        geoapify_places_df = pd.json_normalize(dict(geoapify_places['features']))
    except TimeoutError as e:
        print(f'Timeout Error: {e}')
    return geoapify_places_df

def extract_yelp(file:str = '../../data/yelp_academic_dataset_business.json') -> pd.DataFrame:
    """
        extract yelp training data & return as dataframe
    """
    yelp = pd.read_json(file, lines=True)
    return yelp


# data transformation

def process_geoapify(data:pd.DataFrame) -> pd.DataFrame:
    """
        process geoapify API payload
    """
    places_relevant_columns = ['properties.place_id','properties.name','properties.categories',
                                'properties.opening_hours','properties.country',
                                'properties.state','properties.city'
                                ,'properties.street','properties.postcode',
                                'properties.lon','properties.lat']

    places_rename ={
        'properties.place_id':'place_id',
        'properties.name': 'name',
        'properties.categories': 'categories',
        'properties.country': 'country',
        'properties.state': 'state',
        'properties.city': 'city',
        'properties.street': 'street',
        'properties.postcode': 'postcode',
        'properties.opening_hours':'hours',
        'properties.lon' : 'longitude',
        'properties.lat' : 'latitude'
    }
    places_df_view = data[places_relevant_columns].rename(columns=places_rename)
    places_df_view['hours'] = places_df_view['hours'].apply(format_date)
    return places_df_view

def process_yelp(data:pd.DataFrame)->pd.DataFrame:
    """
        process yelp business training data
    """
    yelp_relevant_columns = ['business_id','name','categories','hours','country',
                                    'state','city','address','postal_code',
                                    'latitude','longitude']
    yelp_rename = {
            'business_id':'place_id',
            'address' : 'street',
            'postal_code':'postcode',
    }
    yelp_business = data.assign(country = 'United States')
    yelp_business['categories'] = yelp_business['categories'].str.split(',')
    yelp_business['hours'] = yelp_business['hours'].apply(format_time)
    yelp_business_df_view = yelp_business[yelp_relevant_columns].rename(columns=yelp_rename)
    return yelp_business_df_view

# mock data generators : user preference

def create_mock_user_preference() -> dict:
    """
        create mock dictionary of user preference form
        values must match the ML pipeline's UserPreference TypedDict exactly —
        wrong keys or values are silently ignored during embedding
    """
    use_case = ['local', 'daytrip', 'travel', 'mixed']
    party_type = ['solo', 'couple', 'friends', 'family', 'mixed']
    daily_budget_tier = [1, 2, 3, 4]
    trip_budget_tier  = [1, 2, 3, 4]
    # underscored to match the place tag enum in place_classifier.py
    preferred_tags = [
        'outdoor', 'cultural', 'food_and_drink', 'nightlife', 'shopping',
        'wellness', 'historical', 'scenic', 'adventurous', 'family_friendly',
        'romantic', 'pet_friendly', 'upscale', 'budget_friendly', 'quick_visit',
    ]
    exploration_score = [1, 2, 3, 4, 5]
    popularity_weight = [1, 2, 3, 4, 5]
    # lowercase to match ALL_CUISINES in user_profiler.py
    cuisine_preferences = [
        'american', 'italian', 'east asian', 'southeast asian',
        'mexican', 'indian', 'mediterranean', 'vegetarian', 'seafood',
    ]
    # underscored to match ALL_DIETARY in user_profiler.py
    dietary_restrictions = [
        'vegetarian', 'vegan', 'gluten_free', 'halal',
        'kosher', 'nut_allergy', 'dairy_free',
    ]
    # short codes to match ALL_TRAVEL_MODES in user_profiler.py
    travel_mode = ['walk', 'bike', 'transit', 'drive']
    max_travel_minutes = ['< 10', '10-20', '20-40', '> 40']
    itinerary_pace = ['packed', 'balanced', 'relaxed']

    user_preference = {}
    user_preference['user_id']              = str(random.randint(1, 100000))
    user_preference['use_case']             = random.choice(use_case)
    user_preference['party_type']           = random.choice(party_type)
    user_preference['daily_budget_tier']    = random.choice(daily_budget_tier)
    user_preference['trip_budget_tier']     = random.choice(trip_budget_tier)
    user_preference['preferred_tags']       = random.sample(preferred_tags, random.randint(1, 3))
    user_preference['exploration_score']    = random.choice(exploration_score)
    user_preference['popularity_weight']    = random.choice(popularity_weight)
    user_preference['cuisine_preferences']  = random.sample(cuisine_preferences, random.randint(1, 3))
    user_preference['dietary_restrictions'] = random.sample(dietary_restrictions, random.randint(0, 2))
    user_preference['travel_mode']          = random.sample(travel_mode, random.randint(1, 2))
    user_preference['max_travel_minutes']   = random.choice(max_travel_minutes)
    user_preference['itinerary_pace']       = random.choice(itinerary_pace)

    return user_preference

# helper functions

def format_date(data:str, delimitter = ';') -> str:
    """
        format dates: Mo-Fr 07:00 - 20:00 ->
        {Monday: 07:00 - 20:00,...,Friday: 07:00 - 20:00}
    """
    if delimitter in data:
        date_list = data.split(delimitter)
    else:
        date = data + delimitter
        date_list = date.split(delimitter)
    if len(date_list) > 1:
        date_list = [date.split(' ') for date in date_list]
        # eliminate spaces
        date_list = [list(filter(None, date)) for date in date_list]
        date_list = [expand_date(date) for date in date_list]
    else:
        date_list = expand_date(date_list)
    if len(date_list) == 4:
        date_list = date_list[0] + date_list[1] + date_list[2] + date_list[3]
    if len(date_list) == 3:
        date_list = date_list[0] + date_list[1] + date_list[2]
    if len(date_list) == 2:
        date_list = date_list[0] + date_list[1]
    date_list = dict(date_list)

    result = str(date_list)

    return result

def expand_date(date:list[str]) -> list:
    """
        Expands Mo-fr to list [Monday,...,Friday]
    """
    day_mapper = {
    'Mo': 'Monday',
    'Tu': 'Tuesday',
    'We': 'Wednesday',
    'Th': 'Thursday',
    'Fr': 'Friday',
    'Sa': 'Saturday',
    'Su': 'Sunday',
    }
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    result = []
    if len(date) != 2:
        return result
    day_part, time_part = date[0],date[1]
    if '-' in day_part and len(day_part) > 2:
        start_day, end_day = day_part.split('-')
        start_full = day_mapper[start_day]
        end_full = day_mapper[end_day]
        if start_full and end_full:
            start_idx = day_order.index(start_full)
            end_idx = day_order.index(end_full)
            for day in day_order[start_idx:end_idx+1]:
                result.append([day, time_part])
    else:
        # Single day
        full_day = day_mapper[day_part]
        if full_day:
            result.append([full_day, time_part])
    return result

def format_time(data):
    """
        format dates with improper time formats
        eg. Monday: 0:0-0:0, Tuesday: 8:0-18:30
    """
    if data is not None:
        data = dict(data)
        for k,v in data.items():
            data[k] = expand_time(v)
    return data

def expand_time(data):
    """
        expand time 0:0 -> 0:00
    """
    result = []
    time_pair = data.split('-')
    for time_str in time_pair:
        hour, minute = time_str.split(':')
        formatted_time = f"{hour}:{minute.zfill(2)}"
        result.append(formatted_time)
    result_str = result[0] +'-'+ result[1]
    return result_str
