# Tuščias bakas – Home Assistant

Home Assistant custom integracija Lietuvos degalinių kainoms iš viešo **tusciasbakas.lt** API.

Duomenų šaltinis: **Lietuvos energetikos agentūra (LEA) ir degalines valdančios įmonės, per tusciasbakas.lt**.

## Galimybės

- pasirinkti paieškos centro koordinates;
- pasirinkti **1–50 km** spindulį;
- pasirinkti kurą: **Benzinas 95, Dyzelinas arba SND**;
- pridėti savo nuolaidas pagal degalinių tinklą ir savaitės dieną;
- matyti pigiausią skelbiamą kainą;
- matyti pigiausią kainą po tavo nuolaidų;
- matyti artimiausią degalinę ir atstumą;
- sensorių atributuose gauti iki 10 geriausių degalinių.

> Atstumas skaičiuojamas tiesia linija (Haversine), ne pagal kelią.

## Diegimas per HACS

1. HACS → Integrations → ⋮ → **Custom repositories**.
2. Repository: `https://github.com/braticks/Homeassistant`
3. Category: **Integration**.
4. Įdiek **Tuščias bakas**.
5. Perkrauk Home Assistant.
6. Settings → Devices & services → Add integration → **Tuščias bakas**.

## Nuolaidų taisyklės

Viena taisyklė = viena eilutė:

```text
Degalinė;dienos;nuolaida_EUR_l
```

Pavyzdžiai:

```text
Circle K;fri;0.10
Neste;mon,tue,wed,thu,fri;0.05
Viada;all;0.03
```

Galima naudoti ir trumpinius lietuviškai:

```text
Circle K;pen;0.10
Neste;pir,ant,tre,ket,pen;0.05
```

Jei tą pačią dieną tai pačiai degalinei tinka kelios taisyklės, jų nuolaidos **sudedamos**.

## Sukuriami sensoriai

- `sensor.tuscias_bakas_pigiausia_skelbiama_kaina`
- `sensor.tuscias_bakas_pigiausia_kaina_su_nuolaidomis`
- `sensor.tuscias_bakas_artimiausia_degaline`
- `sensor.tuscias_bakas_degaliniu_spindulyje`

Tikslūs entity ID gali šiek tiek skirtis pagal Home Assistant kalbą ir jau egzistuojančius entity.

## API

Integracija naudoja:

`https://tusciasbakas.lt/api/v1/stations.json`

Kadangi tai trečiosios šalies viešas API, jo formato pakeitimai gali pareikalauti integracijos atnaujinimo. Parseris specialiai parašytas tolerantiškai keliems dažniausiems JSON / GeoJSON formatams.
