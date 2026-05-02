import random


def create_mock_user_preference() -> dict:
    # random user preference for local testing — values match UserPreference TypedDict exactly
    use_case = ['local', 'daytrip', 'travel', 'mixed']
    party_type = ['solo', 'couple', 'friends', 'family', 'mixed']
    daily_budget_tier = [1, 2, 3, 4]
    trip_budget_tier  = [1, 2, 3, 4]
    preferred_tags = [
        'outdoor', 'cultural', 'food_and_drink', 'nightlife', 'shopping',
        'wellness', 'historical', 'scenic', 'adventurous', 'family_friendly',
        'romantic', 'pet_friendly', 'upscale', 'budget_friendly', 'quick_visit',
    ]
    exploration_score = [1, 2, 3, 4, 5]
    popularity_weight = [1, 2, 3, 4, 5]
    cuisine_preferences = [
        'american', 'italian', 'east asian', 'southeast asian',
        'mexican', 'indian', 'mediterranean', 'vegetarian', 'seafood',
    ]
    dietary_restrictions = [
        'vegetarian', 'vegan', 'gluten_free', 'halal',
        'kosher', 'nut_allergy', 'dairy_free',
    ]
    travel_mode = ['walk', 'bike', 'transit', 'drive']
    max_travel_minutes = ['< 10', '10-20', '20-40', '> 40']
    itinerary_pace = ['packed', 'balanced', 'relaxed']

    return {
        'user_id':              str(random.randint(1, 100000)),
        'use_case':             random.choice(use_case),
        'party_type':           random.choice(party_type),
        'daily_budget_tier':    random.choice(daily_budget_tier),
        'trip_budget_tier':     random.choice(trip_budget_tier),
        'preferred_tags':       random.sample(preferred_tags, random.randint(1, 3)),
        'exploration_score':    random.choice(exploration_score),
        'popularity_weight':    random.choice(popularity_weight),
        'cuisine_preferences':  random.sample(cuisine_preferences, random.randint(1, 3)),
        'dietary_restrictions': random.sample(dietary_restrictions, random.randint(0, 2)),
        'travel_mode':          random.sample(travel_mode, random.randint(1, 2)),
        'max_travel_minutes':   random.choice(max_travel_minutes),
        'itinerary_pace':       random.choice(itinerary_pace),
    }
