# Cached talking states

A fixed view makes the rendered image a function of `(avatar, mouth, blink, expression, size, samples, renderer, Blender version)`. A narration is a sequence of references to those images. No generative image service is used.

There are 9 mouth states × 2 blink states × 4 eyebrow expressions = at most 72 images per render configuration. Render only the subset used by the current narration. A 90-second video at 25 fps has 2,250 output frames, but needs at most 72 Blender renders for that configuration; that is a count bound, not a measured wall-clock speedup. Subsequent identical states cost no Blender renders.

The SHA-256 cache key includes the full `.blend`, `render_states.py`, resolution, sample count and Blender version. The source file includes camera, material and lighting settings; changes to these therefore invalidate cached pixels. Frame rate, text and voice only affect which states are selected. PNGs use alpha so game backgrounds need no invalidation.

Output frame sequences use hard links where available and copies across filesystems. Treat linked PNGs as immutable; never modify a frame file in place. Replace source/model files then render again instead. Scratch caches are disposable and can be reconstructed from the saved bank. Run jobs sequentially when they share the same cache configuration.

Discrete mouth changes deliberately follow Rhubarb cues. Smoother blends, multiple eyelid phases, head poses or graded expressions multiply the state space. Add them only after a visual need is demonstrated and update both planner and renderer together. Do not silently enable per-frame renders, idle motion or random lighting.

Rhubarb's phonetic recognizer supports non-English audio, with basic recognition rather than a guarantee of language-specific phoneme accuracy. See its upstream documentation: https://github.com/DanielSWolf/rhubarb-lip-sync . Transparent Eevee film: https://docs.blender.org/manual/en/5.0/render/eevee/render_settings/film.html .
