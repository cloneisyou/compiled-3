# Space Janitor: 90-second pitch script

For the phone take: you talk to camera, the film plays on the laptop behind you. The script is
**152 words**, about **68 seconds** at a calm 135 words per minute, so there are twenty seconds of
slack for pauses and laughs. It does not need to sync with the film.

`…` is a one-beat pause. **Bold** words carry the stress.

## The script

> YC wants startups for a world of abundant space access. You know what else gets abundant? …
> **Trash.**
>
> Everybody wants to launch a satellite. Nobody wants to take one **out**.
>
> Fun fact: in 2009, two satellites crashed at forty-two thousand kilometers an hour and left
> **two thousand** pieces behind. Space has no garbage day.
>
> So **we're** the garbage day. Space Janitor: the job SpaceX and NASA don't want.
>
> A swarm of tiny mirrors focuses sunlight on a piece of junk until it burns up. No fuel. No
> lasers. Basically a kid with a magnifying glass … and a business model.
>
> Starlink-size fleets pay a subscription to keep their orbit clean. And cheap launch pays us
> **twice**: more trash, cheaper janitors.
>
> Behind me: real debris, real orbits, real prices.
>
> And if there's a satellite you don't like … shame if we **focused** on it. … Legal says I'm
> joking.
>
> Space Janitor. We take out the trash.

## Pace check

| You should be finishing | By about |
|---|---|
| "Space has no garbage day." | 0:24 |
| "…SpaceX and NASA don't want." | 0:30 |
| "…and a business model." | 0:44 |
| "…cheaper janitors." | 0:53 |
| "Legal says I'm joking." | 1:05 |
| "We take out the trash." | 1:08 |

## Delivery notes

- Open flat and serious, then pause before "Trash." That is the first laugh.
- "Space has no garbage day." and "So we're the garbage day." are a call and response: land the
  first, breathe, then answer it.
- Slow down for "No fuel. No lasers." Two separate sentences. Then throw away "and a business
  model" as an afterthought.
- On "Behind me", glance or point back at the laptop.
- Say the threat line quietly and deadpan, then smile on "Legal says I'm joking."

## 한국어 번역 (참고용)

> YC가 "우주 접근이 풍부해진 세상의 스타트업"을 찾는다죠. 그때 같이 풍부해지는 게 뭔지 아세요?
> 쓰레기입니다.
>
> 위성을 쏘고 싶은 사람은 많은데, 치우고 싶은 사람은 없어요.
>
> Fun fact: 2009년에 위성 두 대가 시속 4만 2천 km로 부딪쳐서 파편 2천 개를 남겼습니다. 우주에는
> 쓰레기 수거일이 없거든요.
>
> 그래서 저희가 그 수거일입니다. Space Janitor, SpaceX도 NASA도 하기 싫어하는 일이죠.
>
> 작은 거울 군집이 쓰레기 한 조각에 햇빛을 모아 태워 버립니다. 연료도 레이저도 없이. 돋보기 든
> 아이랑 똑같아요… 수익 모델이 있을 뿐이죠.
>
> 스타링크급 위성군이 궤도를 깨끗하게 유지하려고 구독료를 냅니다. 그리고 발사가 싸지면 저희는 두 번
> 법니다. 쓰레기는 늘고, 미화원은 싸지니까요.
>
> 제 뒤에 보이는 건 실제 파편, 실제 궤도, 실제 가격입니다.
>
> 그리고 마음에 안 드는 위성이 있다면… 저희가 초점이라도 맞추면 큰일이겠죠. 법무팀이 농담이라고
> 하랍니다.
>
> Space Janitor. 쓰레기는 저희가 내다 버립니다.

## If a judge asks "does it really burn?"

> A hundred one-meter mirrors from a hundred meters put about 42 kilowatts per square meter on the
> target. That is around 930 kelvin, right at aluminum's melting point, and well past where
> insulation foil and paint break down. Four hundred mirrors reach 1,300 kelvin. More mirrors is
> exactly what cheap launch buys us, and you can try any object in our calculator.

## What the film shows (`video/space-janitor-90s.mp4`)

| Time | On screen |
|---|---|
| 0:00 to 0:08 | The Sun, then Earth with rockets leaving in every direction. |
| 0:08 to 0:24 | A field of tumbling junk; two dead objects collide (the 2009 fun fact). |
| 0:24 to 0:37 | One mirror satellite, then the swarm deploying into a dish formation. |
| 0:37 to 0:47 | Close-up of the gold mirror segments; the swarm turns to a dead satellite. |
| 0:47 to 1:00 | Beams converge, the satellite glows, vaporizes, and falls as a fireball. |
| 1:00 to 1:12 | The simulator and pricing calculator from `app/`, running on real debris orbits. |
| 1:12 to 1:24 | "RIVAL CORP" gets the same treatment. "oops." |
| 1:24 to 1:30 | Logo and tagline. |

## Numbers behind the lines

- **A hundred times cheaper**: the premise of YC's request, based on reusable Starship.
- **Fun fact (2009)**: Iridium 33 and the dead Kosmos 2251 collided at about 11.7 km/s
  (42,000 km/h) and left more than 2,000 catalogued fragments. The simulator loads those fragments.
- **Burns up**: 100 mirrors of 1 m² collect 136 kW of sunlight and deliver about 122 kW. The Sun
  is 0.53° wide, so from 100 m away the spot is about 1.9 m across: roughly 42 kW/m², which settles
  near 930 K, right at aluminum's melting point (933 K). About 400 mirrors reach 1,300 K. The
  calculator in `app/` shows the numbers for any object.
- **Slows down**: vaporizing material pushes back like a tiny rocket. Aimed against the orbit, it
  lowers the perigee until drag finishes the job. Same idea as laser ablation, with no laser.
