# PlanIt — ML Pipeline

**Team:** Ahmed Abdelsalam, Dennes Lopez, Sifatun Noor, Kripamoye Biswas

---

## Folder Structure

```
TO BE UPDATED

---

## Pipeline Stages

| Stage | Description                                                                                  | Status      |
| ----- | -------------------------------------------------------------------------------------------- | ----------- |
| 1     | Place tagging — maps Geoapify category strings to 15 semantic tags                           | Done        |
| 2     | User profiling — blends survey encoding with collaborative filtering into a 64-dim embedding | Done        |
| 3     | Recommendation engine — ranks candidate places against the user embedding                    | Done        |
| 4     | Itinerary optimizer — schedules ranked places into a day-by-day plan via OR-Tools VRP        | In progress |
