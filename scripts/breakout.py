"""Mask-guided pop-out layout; semantic subject selection belongs to the author."""


def resolve_layout(plan, directory, magick, dimensions, resolve_source, require):
    source = resolve_source(plan.get('source'), directory)
    mask = resolve_source(plan.get('foreground_mask'), directory)
    width, height = dimensions(source)
    require(width * height <= 80_000_000, 'Source exceeds the local pixel budget.')
    require(dimensions(mask) == (width, height), 'Foreground mask must match the source dimensions.')
    require(plan.get('fit', 'exact') == 'exact', 'Prepare source and mask together; breakout uses exact pixels.')
    require(plan.get('height', height) == height, 'Breakout height must match the source.')
    layout = plan.get('layout', 'hybrid')
    require(layout in ('hybrid', 'uniform', 'adaptive'), 'layout must be hybrid, uniform or adaptive.')
    mask_pixels = magick(mask, '-background', 'black', '-alpha', 'remove', '-alpha', 'off',
                         '-colorspace', 'gray', '-depth', '8', 'gray:-')
    columns = [False] * width
    min_y, max_y = height, -1
    for index, strength in enumerate(mask_pixels):
        if strength:
            columns[index % width] = True
            min_y = min(min_y, index // width)
            max_y = max(max_y, index // width)
    occupied = [x for x, selected in enumerate(columns) if selected]
    require(occupied, 'Foreground mask is empty; select a meaningful subject first.')
    bounds = [occupied[0], min_y, occupied[-1] + 1, max_y + 1]
    if layout == 'hybrid':
        column_count = plan.get('column_count', 20)
        column_width = plan.get('column_width', 80)
        gap = plan.get('gap_width', 8)
        require(type(column_count) is int and 2 <= column_count <= 100, 'column_count must be 2–100.')
        require(type(column_width) is int and column_width > 0 and type(gap) is int and gap > 0,
                'column_width and gap_width must be positive integers.')
        require(not any(key in plan for key in ('width', 'widths', 'bar_width')),
                'Hybrid layout uses column_width; attachment widths are derived from the shared grid.')
        pitch = column_width + gap
        require(width == column_count * column_width + (column_count - 1) * gap,
                'Prepare source and mask at column_count * column_width + (column_count - 1) * gap_width.')
        padding = plan.get('subject_padding', 0)
        require(type(padding) is int and padding >= 0, 'subject_padding must be nonnegative.')
        first = max(0, bounds[0] - padding) // pitch
        last = min(width - 1, bounds[2] - 1 + padding) // pitch
        if min(width, bounds[2] + padding) > last * pitch + column_width:
            last += 1
        groups = [(i, i) for i in range(first)] + [(first, last)]
        groups += [(i, i) for i in range(last + 1, column_count)]
        require(2 <= len(groups) <= 20,
                'Hybrid grid needs 2–20 attachments; adjust composition or column_count, never cut the subject.')
        require('count' not in plan or plan['count'] == len(groups),
                'count is actual attachments, not visible columns; omit count or use the derived value.')
        crops = [[a * pitch, (b - a + 1) * column_width + (b - a) * gap] for a, b in groups]
        return dict(plan, layout=layout, count=len(groups), height=height,
                    widths=[crop[1] for crop in crops], column_count=column_count,
                    column_width=column_width, bar_width=column_width, gap_width=gap,
                    _source_width=width, _crop_ranges=crops, _foreground_bounds=bounds,
                    _subject_cut_positions=[], _main_columns=[first, last],
                    _main_attachment=first + 1)
    count = plan.get('count', 20)
    require(type(count) is int and 2 <= count <= 20, 'Breakout requires 2–20 attachments.')
    widths = plan.get('widths')
    if layout == 'uniform':
        panel_width = plan.get('width', 80)
        require(type(panel_width) is int and panel_width > 0, 'width must be a positive integer.')
        require(width == count * panel_width,
                f'Uniform layout needs a {count * panel_width}px-wide source and matching mask. '
                'Prepare both at the same scale first; do not stretch individual slices.')
        if widths is not None:
            require(widths == [panel_width] * count, 'Uniform layout rejects unequal widths.')
        widths = [panel_width] * count
    else:
        require('width' not in plan, 'Adaptive layout uses widths, not width.')
    if widths is None:
        padding = plan.get('subject_padding', max(1, round(width * .015)))
        minimum = plan.get('min_panel_width', max(1, width // 100))
        require(type(padding) is int and padding >= 0, 'subject_padding must be a nonnegative integer.')
        require(type(minimum) is int and minimum > 0, 'min_panel_width must be positive.')
        left = max(0, bounds[0] - padding)
        right = max(0, width - bounds[2] - padding)
        left_capacity, right_capacity = left // minimum, right // minimum
        require(left_capacity + right_capacity >= count - 1,
                'Not enough background beside the subject. Reduce count, refine the mask, or choose another mode.')
        left_count = round((count - 1) * left / (left + right))
        left_count = max(count - 1 - right_capacity, min(left_count, left_capacity, count - 1))
        right_count = count - 1 - left_count
        cuts = [round(left * i / left_count) for i in range(1, left_count + 1)] if left_count else []
        if right_count:
            cuts += [width - right + round(right * i / right_count) for i in range(right_count)]
        edges = [0] + cuts + [width]
        widths = [b - a for a, b in zip(edges, edges[1:])]
    require(isinstance(widths, list) and len(widths) == count and
            all(type(n) is int and n > 0 for n in widths) and sum(widths) == width,
            'widths must contain count positive integers summing to the source width.')
    cuts, position = [], 0
    for panel_width in widths[:-1]:
        position += panel_width
        cuts.append(position)
    # Real attachment gutters cannot be covered by pixels in another attachment.
    subject_cuts = [cut for cut in cuts if bounds[0] < cut < bounds[2]]
    allow_subject_cuts = plan.get('allow_subject_cuts', layout == 'uniform')
    require(type(allow_subject_cuts) is bool, 'allow_subject_cuts must be boolean.')
    require(allow_subject_cuts or not subject_cuts,
            'An attachment cut crosses the protected foreground span. Choose a compatible composition or explicitly change the layout.')
    resolved = dict(plan, count=count, height=height, widths=widths, layout=layout)
    if layout == 'uniform':
        resolved['width'] = panel_width
    resolved['_foreground_bounds'] = bounds
    resolved['_subject_cut_positions'] = subject_cuts
    return resolved


def compose_master(plan, directory, scratch, magick, dimensions, resolve_source, require):
    width, height = plan.get('_source_width', sum(plan['widths'])), plan['height']
    source = resolve_source(plan['source'], directory)
    mask = resolve_source(plan['foreground_mask'], directory)
    if plan['layout'] == 'uniform':
        gap_width = plan.get('gap_width', max(1, round(plan['width'] * .10)))
        bar_width = plan.get('bar_width', plan['width'] - gap_width)
    else:
        bar_width = plan.get('bar_width', max(2, round(width / 12)))
        gap_width = plan.get('gap_width', max(1, round(bar_width * .10)))
    radius = plan.get('corner_radius', min(bar_width // 2, gap_width * 2))
    require(type(bar_width) is int and 1 <= bar_width < width, 'bar_width must be smaller than the source width.')
    require(type(gap_width) is int and 1 <= gap_width < width, 'gap_width must be positive and smaller than the source.')
    require(type(radius) is int and 0 <= radius <= min(bar_width // 2, height // 2), 'Invalid corner_radius.')
    stripe_mask, subject_mask = scratch / 'stripes.png', scratch / 'subject.png'
    keep_mask, alpha_mask = scratch / 'keep.png', scratch / 'alpha.png'
    commands = []
    for start in range(0, width, bar_width + gap_width):
        end = min(width - 1, start + bar_width - 1)
        local_radius = min(radius, (end - start) // 2)
        commands.append(f'roundrectangle {start},0 {end},{height-1} {local_radius},{local_radius}')
    magick('-size', f'{width}x{height}', 'xc:black', '-fill', 'white', '-draw', ' '.join(commands), stripe_mask)
    magick(mask, '-background', 'black', '-alpha', 'remove', '-alpha', 'off', '-colorspace', 'gray', subject_mask)
    magick(stripe_mask, subject_mask, '-compose', 'Lighten', '-composite', keep_mask)
    magick(source, '-alpha', 'extract', keep_mask, '-compose', 'Multiply', '-composite', alpha_mask)
    master = scratch / 'breakout-master.png'
    magick(source, alpha_mask, '-alpha', 'off', '-compose', 'CopyOpacity', '-composite', '-strip', master)
    original = magick(source, '-alpha', 'on', '-depth', '8', 'rgba:-')
    composed = magick(master, '-alpha', 'on', '-depth', '8', 'rgba:-')
    protected = magick(subject_mask, '-depth', '8', 'gray:-')
    protected_count, preserved = 0, True
    for index, strength in enumerate(protected):
        if strength == 255:
            protected_count += 1
            offset = index * 4
            preserved = preserved and original[offset:offset+4] == composed[offset:offset+4]
    require(protected_count > 0, 'Mask needs a fully white foreground core, not only faint gray.')
    require(preserved, 'Compositing changed protected foreground pixels.')
    transparent_count = sum(alpha == 0 for alpha in composed[3::4])
    # A mask covering every stripe gap gives no visible pop-out effect.
    require(transparent_count > 0, 'No transparent background gaps remain; revise the mask or stripe spacing.')
    report = {'foreground_bounds': plan['_foreground_bounds'], 'layout': plan['layout'],
              'subject_cut_positions': plan['_subject_cut_positions'],
              'bar_width': bar_width,
              'gap_width': gap_width, 'corner_radius': radius,
              'fully_protected_pixels': protected_count, 'foreground_pixels_preserved': preserved,
              'transparent_pixels': transparent_count,
              'subject_selection': 'author-supplied mask; not automatic semantic detection'}
    if plan['layout'] == 'hybrid':
        report.update(column_count=plan['column_count'], column_width=plan['column_width'],
                      main_columns=plan['_main_columns'], main_attachment=plan['_main_attachment'],
                      crop_ranges=plan['_crop_ranges'], source_width=width,
                      real_gaps_baked_into_files=False)
    return master, report
