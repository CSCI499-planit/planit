import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import "../components/survey.css";
import {
  Trees,
  Utensils,
  Music2,
  ShoppingBag,
  Dumbbell,
  Landmark,
  Camera,
  Mountain,
  Users,
  Heart,
  PawPrint,
  Gem,
  Wallet,
} from "lucide-react";

export default function SurveyPage() {
  const navigate = useNavigate();

  const [answers, setAnswers] = useState({
    use_case: "",
    party_type: "",
    daily_budget_tier: "",
    trip_budget_tier: "",
    preferred_tags: [],
    exploration_score: 3,
    popularity_weight: 3,
    cuisine_preferences: [],
    dietary_restrictions: [],
    travel_mode: "",
    max_travel_minutes: "",
    itinerary_pace: "",
    maps_history: "",
  });

  const set = (key, val) => setAnswers((prev) => ({ ...prev, [key]: val }));

  const toggleList = (key, val) => {
    setAnswers((prev) => ({
      ...prev,
      [key]: prev[key].includes(val)
        ? prev[key].filter((v) => v !== val)
        : [...prev[key], val],
    }));
  };

  // maps display labels to ML schema values to avoid mismatches in the backend
  const USE_CASE_MAP = {
    local: "local",
    day: "daytrip",
    long: "travel",
    all: "mixed",
  };

  const TRAVEL_MODE_MAP = {
    Walking: "walk",
    Biking: "bike",
    "Public Transit": "transit",
    Driving: "drive",
  };

  const CUISINE_MAP = {
    American: "american",
    Italian: "italian",
    "East Asian": "east asian",
    "Southeast Asian": "southeast asian",
    "Mexican/Latin American": "mexican",
    "Indian/South Asian": "indian",
    "Mediterranean/Middle Eastern": "mediterranean",
    "Vegetarian Focus": "vegetarian",
    "Seafood Focus": "seafood",
  };

  const DIETARY_MAP = {
    Vegetarian: "vegetarian",
    Vegan: "vegan",
    "Gluten-free": "gluten_free",
    Halal: "halal",
    Kosher: "kosher",
    "Nut allergy": "nut_allergy",
    "Dairy-free": "dairy_free",
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const mappedMode = TRAVEL_MODE_MAP[answers.travel_mode];

    const normalized = {
      ...answers,
      use_case: USE_CASE_MAP[answers.use_case] ?? answers.use_case,
      daily_budget_tier: Number(answers.daily_budget_tier),
      trip_budget_tier:
        answers.trip_budget_tier === "0"
          ? null
          : Number(answers.trip_budget_tier),
      travel_mode: mappedMode ? [mappedMode] : [],
      cuisine_preferences: answers.cuisine_preferences.map(
        (c) => CUISINE_MAP[c] ?? c,
      ),
      dietary_restrictions: answers.dietary_restrictions
        .filter((d) => d !== "None")
        .map((d) => DIETARY_MAP[d] ?? d),
      itinerary_pace: answers.itinerary_pace.toLowerCase(),
      max_travel_minutes: answers.max_travel_minutes.replace(" min", ""),
    };

    const payload = { ...normalized };
    delete payload.maps_history;

    localStorage.setItem("userPreferences", JSON.stringify(payload));

    try {
      await api.post("/preference/", payload);
    } catch (err) {
      console.error("Failed to save preferences to backend:", err.message);
    }

    if (answers.maps_history === "yes") {
      navigate("/upload");
    } else {
      navigate("/app/home");
    }
  };

  const interests = [
    { id: "outdoor", label: "Outdoor adventures (hiking, parks, nature)", icon: <Trees size={16} />},
    { id: "cultural", label: "Art, galleries, museums & cultural experiences", icon: <Landmark size={16} />},
    { id: "food_and_drink", label: "Restaurants, cafes, culinary spots", icon: <Utensils size={16} /> },
    { id: "nightlife", label: "Bars, live music, comedy shows & nightlife", icon: <Music2 size={16} /> },
    { id: "shopping", label: "Shopping, markets, thrift stores", icon: <ShoppingBag size={16} /> },
    { id: "wellness", label: "Fitness, meditation, yoga", icon: <Dumbbell size={16} /> },
    { id: "historical", label: "History, architecture & heritage sites", icon: <Camera size={16} /> },
    { id: "scenic", label: "Scenic spots & viewpoints", icon: <Heart size={16} /> },
    { id: "adventurous", label: "Adventurous activities", icon: <Mountain size={16} /> },
    { id: "family_friendly", label: "Family-friendly spots", icon: <Users size={16} />  },
    { id: "romantic", label: "Romantic settings", icon: <Heart size={16} /> },
    { id: "pet_friendly", label: "Dog-friendly spaces", icon: <PawPrint size={16} /> },
    { id: "upscale", label: "Upscale & luxury places", icon: <Gem size={16} /> },
    { id: "budget_friendly", label: "Budget-friendly spots", icon: <Wallet size={16} /> },
  ];

  const cuisines = [
    "American",
    "Italian",
    "East Asian",
    "Southeast Asian",
    "Mexican/Latin American",
    "Indian/South Asian",
    "Mediterranean/Middle Eastern",
    "Vegetarian Focus",
    "Seafood Focus",
  ];

  const dietary = [
    "Vegetarian",
    "Vegan",
    "Gluten-free",
    "Halal",
    "Kosher",
    "Nut allergy",
    "Dairy-free",
    "None",
  ];

  const completedFields = [
    answers.use_case,
    answers.party_type,
    answers.daily_budget_tier,
    answers.trip_budget_tier,
    answers.preferred_tags.length > 0,
    answers.exploration_score,
    answers.popularity_weight,
    answers.cuisine_preferences.length > 0,
    answers.dietary_restrictions.length > 0,
    answers.travel_mode,
    answers.max_travel_minutes,
    answers.itinerary_pace,
    answers.maps_history,
  ].filter(Boolean).length;
  
  const totalFields = 13;
  const progress = Math.round((completedFields / totalFields) * 100
  );

  return (
    <div className="survey-page">
      <div className="survey-progress-wrapper">
        <div className="survey-progress-top">
          <span>TRAVEL PROFILE</span>
          <span>{progress}% COMPLETE</span>
        </div>

        <div className="survey-progress-bar">
          <div
            className="survey-progress-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

{/* Additions: can add subtexts for questions that are multi-select*/}
      <div className="survey-container">
        <h1>Personalize Your Experience</h1>
          <p className="survey-subtitle">
            Set up your travel profile to allow personalized recommendations.
          </p>

        <form onSubmit={handleSubmit} className="survey-form">
          {/* 1 */}
          <fieldset>
            <legend>1. What will you mostly use PlanIt for?</legend>
            <div className="radio-group">
              {[
                ["local", "Discovering things to do locally"],
                ["day", "Day trips or short outings outside my city"],
                ["long", "Planning long trips (overnight/multiday)"],
                ["all", "All of the above"],
              ].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="use_case"
                    value={val}
                    checked={answers.use_case === val}
                    onChange={(e) => set("use_case", e.target.value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 2 */}
          <fieldset>
            <legend>2. Who are you usually planning for?</legend>
            <div className="radio-group">
              {[
                ["solo", "Myself (solo)"],
                ["couple", "Me and a partner (couple)"],
                ["friends", "Group of friends"],
                ["family", "Family with kids"],
                ["mixed", "Multiple/Varying groups"],
              ].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="party_type"
                    value={val}
                    checked={answers.party_type === val}
                    onChange={(e) => set("party_type", e.target.value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 3 */}
          <fieldset>
            <legend>3. Spending comfort for a day out</legend>
            <div className="radio-group">
              {[
                ["1", "Free or nearly free"],
                ["2", "Budget-conscious"],
                ["3", "Moderate"],
                ["4", "Comfortable"],
                ["5", "No limit"],
              ].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="daily_budget_tier"
                    value={val}
                    checked={answers.daily_budget_tier === val}
                    onChange={(e) => set("daily_budget_tier", e.target.value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 4 */}
          <fieldset>
            <legend>4. Long trip budget</legend>
            <div className="radio-group">
              {[
                ["1", "Budget (< $500)"],
                ["2", "Moderate ($500 - $1,500)"],
                ["3", "Comfortable ($1,500 - $3,000)"],
                ["4", "Luxury ($3,000+)"],
                ["0", "Not applicable"],
              ].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="trip_budget_tier"
                    value={val}
                    checked={answers.trip_budget_tier === val}
                    onChange={(e) => set("trip_budget_tier", e.target.value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 5 */}
          <fieldset>
            <legend>5. Activities</legend>
            <div className="checkbox-grid">
              {interests.map((i) => (
                <label key={i.id}>
                  <input
                    type="checkbox"
                    checked={answers.preferred_tags.includes(i.id)}
                    onChange={() => toggleList("preferred_tags", i.id)}
                  />
                  <>
                    <span className="chip-icon">{i.icon}</span>
                    <span>{i.label}</span>
                  </>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 6 */}
          <fieldset>
            <legend>
              6. Trying new places ({answers.exploration_score}/5)
            </legend>
            <input
              className="slider"
              type="range"
              min="1"
              max="5"
              value={answers.exploration_score}
              onChange={(e) => set("exploration_score", Number(e.target.value))}
            />
          </fieldset>

          {/* 7 */}
          <fieldset>
            <legend>
              7. Importance of popularity ({answers.popularity_weight}/5)
            </legend>
            <input
              className="slider"
              type="range"
              min="1"
              max="5"
              value={answers.popularity_weight}
              onChange={(e) => set("popularity_weight", Number(e.target.value))}
            />
          </fieldset>

          {/* 8 */}
          <fieldset>
            <legend>8. Preferred cuisines</legend>
            <div className="checkbox-grid">
              {cuisines.map((c) => (
                <label key={c}>
                  <input
                    type="checkbox"
                    checked={answers.cuisine_preferences.includes(c)}
                    onChange={() => toggleList("cuisine_preferences", c)}
                  />
                  <span>{c}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 9 */}
          <fieldset>
            <legend>9. Dietary restrictions</legend>
            <div className="checkbox-grid">
              {dietary.map((d) => (
                <label key={d}>
                  <input
                    type="checkbox"
                    checked={answers.dietary_restrictions.includes(d)}
                    onChange={() => toggleList("dietary_restrictions", d)}
                  />
                  <span>{d}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 10 */}
          <fieldset>
            <legend>10. How do you usually get around?</legend>
            <div className="radio-group">
              {["Walking", "Biking", "Public Transit", "Driving", "Other"].map(
                (m) => (
                  <label key={m}>
                    <input
                      type="radio"
                      name="travel_mode"
                      value={m}
                      checked={answers.travel_mode === m}
                      onChange={(e) => set("travel_mode", e.target.value)}
                    />
                    <span>{m}</span>
                  </label>
                ),
              )}
            </div>
          </fieldset>

          {/* 11 */}
          <fieldset>
            <legend>11. How far are you willing to travel?</legend>
            <div className="radio-group">
              {["<10 min", "10-20 min", "20-40 min", ">40 min"].map((v) => (
                <label key={v}>
                  <input
                    type="radio"
                    name="max_travel_minutes"
                    value={v}
                    checked={answers.max_travel_minutes === v}
                    onChange={(e) => set("max_travel_minutes", e.target.value)}
                  />
                  <span>{v}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 12 */}
          <fieldset>
            <legend>12. Preferred pace</legend>
            <div className="radio-group">
              {["Packed", "Balanced", "Relaxed"].map((v) => (
                <label key={v}>
                  <input
                    type="radio"
                    name="itinerary_pace"
                    value={v}
                    checked={answers.itinerary_pace === v}
                    onChange={(e) => set("itinerary_pace", e.target.value)}
                  />
                  <span>{v}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* 13 */}
          <fieldset>
            <legend>13. Upload Google Maps history?</legend>
            <div className="radio-group">
              {[
                [
                  "yes",
                  "Yes, upload my Google Maps history for better personalization",
                ],
                ["no", "No, skip this step"],
              ].map(([val, label]) => (
                <label key={val}>
                  <input
                    type="radio"
                    name="maps_history"
                    value={val}
                    checked={answers.maps_history === val}
                    onChange={(e) => set("maps_history", e.target.value)}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </fieldset>

          {/* Submit */}
          <button type="submit" className="survey-btn">
            Get Recommendations
          </button>
        </form>
      </div>
    </div>
  );
}
