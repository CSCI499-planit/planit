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
  AlertCircle,
  AlertTriangle,
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

  const [errors, setErrors] = useState({});
  const [showBanner, setShowBanner] = useState(false);

  const set = (key, val) => {
    setAnswers((prev) => ({ ...prev, [key]: val }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: null }));
  };

  const toggleList = (key, val) => {
    setAnswers((prev) => {
      const next = prev[key].includes(val)
        ? prev[key].filter((v) => v !== val)
        : [...prev[key], val];
      if (errors[key] && next.length > 0)
        setErrors((e) => ({ ...e, [key]: null }));
      return { ...prev, [key]: next };
    });
  };

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

  const validate = (ans) => {
    const e = {};
    if (!ans.use_case) e.use_case = "Please select an option.";
    if (!ans.party_type) e.party_type = "Please select an option.";
    if (!ans.daily_budget_tier) e.daily_budget_tier = "Please select a budget.";
    if (!ans.trip_budget_tier) e.trip_budget_tier = "Please select a budget.";
    if (ans.preferred_tags.length === 0) e.preferred_tags = "Select at least one activity.";
    if (ans.cuisine_preferences.length === 0) e.cuisine_preferences = "Select at least one cuisine.";
    if (ans.dietary_restrictions.length === 0)
      e.dietary_restrictions = 'Select at least one option (choose "None" if no restrictions).';
    if (!ans.travel_mode) e.travel_mode = "Please select a travel mode.";
    if (!ans.max_travel_minutes) e.max_travel_minutes = "Please select a distance.";
    if (!ans.itinerary_pace) e.itinerary_pace = "Please select a pace.";
    if (!ans.maps_history) e.maps_history = "Please choose an option.";
    return e;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const newErrors = validate(answers);
    setErrors(newErrors);

    const errorCount = Object.keys(newErrors).length;
    if (errorCount > 0) {
      setShowBanner(true);
      setTimeout(() => {
        const firstError = document.querySelector(".survey-fieldset--error");
        firstError?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 50);
      return;
    }

    setShowBanner(false);

    const mappedMode = TRAVEL_MODE_MAP[answers.travel_mode];

    const normalized = {
      ...answers,
      use_case: USE_CASE_MAP[answers.use_case] ?? answers.use_case,
      daily_budget_tier: Number(answers.daily_budget_tier),
      trip_budget_tier:
        answers.trip_budget_tier === "0" ? null : Number(answers.trip_budget_tier),
      travel_mode: mappedMode ? [mappedMode] : [],
      cuisine_preferences: answers.cuisine_preferences.map((c) => CUISINE_MAP[c] ?? c),
      dietary_restrictions: answers.dietary_restrictions
        .filter((d) => d !== "None")
        .map((d) => DIETARY_MAP[d] ?? d),
      itinerary_pace: answers.itinerary_pace.toLowerCase(),
      max_travel_minutes: answers.max_travel_minutes.replace(" min", ""),
    };

    const { maps_history, ...payload } = normalized;
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
    { id: "outdoor", label: "Outdoor adventures (hiking, parks, nature)", icon: <Trees size={16} /> },
    { id: "cultural", label: "Art, galleries, museums & cultural experiences", icon: <Landmark size={16} /> },
    { id: "food_and_drink", label: "Restaurants, cafes, culinary spots", icon: <Utensils size={16} /> },
    { id: "nightlife", label: "Bars, live music, comedy shows & nightlife", icon: <Music2 size={16} /> },
    { id: "shopping", label: "Shopping, markets, thrift stores", icon: <ShoppingBag size={16} /> },
    { id: "wellness", label: "Fitness, meditation, yoga", icon: <Dumbbell size={16} /> },
    { id: "historical", label: "History, architecture & heritage sites", icon: <Camera size={16} /> },
    { id: "scenic", label: "Scenic spots & viewpoints", icon: <Heart size={16} /> },
    { id: "adventurous", label: "Adventurous activities", icon: <Mountain size={16} /> },
    { id: "family_friendly", label: "Family-friendly spots", icon: <Users size={16} /> },
    { id: "romantic", label: "Romantic settings", icon: <Heart size={16} /> },
    { id: "pet_friendly", label: "Dog-friendly spaces", icon: <PawPrint size={16} /> },
    { id: "upscale", label: "Upscale & luxury places", icon: <Gem size={16} /> },
    { id: "budget_friendly", label: "Budget-friendly spots", icon: <Wallet size={16} /> },
  ];

  const cuisines = [
    "American", "Italian", "East Asian", "Southeast Asian",
    "Mexican/Latin American", "Indian/South Asian",
    "Mediterranean/Middle Eastern", "Vegetarian Focus", "Seafood Focus",
  ];

  const dietary = [
    "Vegetarian", "Vegan", "Gluten-free", "Halal",
    "Kosher", "Nut allergy", "Dairy-free", "None",
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
  const progress = Math.round((completedFields / totalFields) * 100);

  const errorCount = Object.keys(errors).length;

  // Fieldset class helper
  const fs = (key) =>
    `survey-fieldset${errors[key] ? " survey-fieldset--error" : ""}`;

  // Inline error component
  const FieldError = ({ field }) =>
    errors[field] ? (
      <p className="survey-field-error">
        <AlertCircle size={13} />
        {errors[field]}
      </p>
    ) : null;

  return (
    <div className="survey-page">
      <div className="survey-progress-wrapper">
        <div className="survey-progress-top">
          <span>TRAVEL PROFILE</span>
          <span>{progress}% COMPLETE</span>
        </div>
        <div className="survey-progress-bar">
          <div className="survey-progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="survey-container">
        <h1>Personalize Your Experience</h1>
        <p className="survey-subtitle">
          Set up your travel profile to allow personalized recommendations.{" "}
          <span className="survey-required-note">
            <span className="survey-required-star">*</span> All questions are required.
          </span>
        </p>

        <form onSubmit={handleSubmit} className="survey-form" noValidate>

          {/* 1 */}
          <fieldset className={fs("use_case")}>
            <legend>
              1. What will you mostly use PlanIt for?
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="use_case" />
          </fieldset>

          {/* 2 */}
          <fieldset className={fs("party_type")}>
            <legend>
              2. Who are you usually planning for?
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="party_type" />
          </fieldset>

          {/* 3 */}
          <fieldset className={fs("daily_budget_tier")}>
            <legend>
              3. Spending comfort for a day out
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="daily_budget_tier" />
          </fieldset>

          {/* 4 */}
          <fieldset className={fs("trip_budget_tier")}>
            <legend>
              4. Long trip budget
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="trip_budget_tier" />
          </fieldset>

          {/* 5 */}
          <fieldset className={fs("preferred_tags")}>
            <legend>
              5. Activities
              <span className="survey-required-star" aria-hidden="true"> *</span>
              <span className="survey-legend-sub"> — pick all that apply</span>
            </legend>
            <div className="checkbox-grid">
              {interests.map((i) => (
                <label key={i.id}>
                  <input
                    type="checkbox"
                    checked={answers.preferred_tags.includes(i.id)}
                    onChange={() => toggleList("preferred_tags", i.id)}
                  />
                  <span className="chip-icon">{i.icon}</span>
                  <span>{i.label}</span>
                </label>
              ))}
            </div>
            <FieldError field="preferred_tags" />
          </fieldset>

          {/* 6 — slider, always valid */}
          <fieldset>
            <legend>6. Trying new places ({answers.exploration_score}/5)</legend>
            <input
              className="slider"
              type="range"
              min="1"
              max="5"
              value={answers.exploration_score}
              onChange={(e) => set("exploration_score", Number(e.target.value))}
            />
          </fieldset>

          {/* 7 — slider, always valid */}
          <fieldset>
            <legend>7. Importance of popularity ({answers.popularity_weight}/5)</legend>
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
          <fieldset className={fs("cuisine_preferences")}>
            <legend>
              8. Preferred cuisines
              <span className="survey-required-star" aria-hidden="true"> *</span>
              <span className="survey-legend-sub"> — pick all that apply</span>
            </legend>
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
            <FieldError field="cuisine_preferences" />
          </fieldset>

          {/* 9 */}
          <fieldset className={fs("dietary_restrictions")}>
            <legend>
              9. Dietary restrictions
              <span className="survey-required-star" aria-hidden="true"> *</span>
              <span className="survey-legend-sub"> — select "None" if not applicable</span>
            </legend>
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
            <FieldError field="dietary_restrictions" />
          </fieldset>

          {/* 10 */}
          <fieldset className={fs("travel_mode")}>
            <legend>
              10. How do you usually get around?
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
            <div className="radio-group">
              {["Walking", "Biking", "Public Transit", "Driving", "Other"].map((m) => (
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
              ))}
            </div>
            <FieldError field="travel_mode" />
          </fieldset>

          {/* 11 */}
          <fieldset className={fs("max_travel_minutes")}>
            <legend>
              11. How far are you willing to travel?
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="max_travel_minutes" />
          </fieldset>

          {/* 12 */}
          <fieldset className={fs("itinerary_pace")}>
            <legend>
              12. Preferred pace
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
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
            <FieldError field="itinerary_pace" />
          </fieldset>

          {/* 13 */}
          <fieldset className={fs("maps_history")}>
            <legend>
              13. Upload Google Maps history?
              <span className="survey-required-star" aria-hidden="true"> *</span>
            </legend>
            <div className="radio-group">
              {[
                ["yes", "Yes, upload my Google Maps history for better personalization"],
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
            <FieldError field="maps_history" />
          </fieldset>

          <button type="submit" className="survey-btn">
            Get Recommendations
          </button>
        </form>
      </div>
    </div>
  );
}