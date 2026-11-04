"""Shared collection contract; validation never follows instructions in source text."""
def normalize_gaps(value):
    if not isinstance(value, list):
        raise ValueError('Coverage gaps must be a list')
    output=[]
    for gap in value:
        if isinstance(gap,str):
            output.append(gap)
        elif isinstance(gap,dict):
            import json
            message=next((gap[key] for key in ('issue','reason','detail','details','message')
                          if isinstance(gap.get(key),str)),json.dumps(gap,sort_keys=True))
            output.append(str(gap.get('category',gap.get('type','coverage'))) + ': ' + message)
        else:
            raise ValueError('Invalid coverage gap')
    return output


def validate_bundle(bundle):
    if not isinstance(bundle,dict) or not isinstance(bundle.get('items'),list):
        raise ValueError('Collection requires items list')
    if type(bundle.get('coverage_complete')) is not bool:
        raise ValueError('Coverage completeness requires boolean')
    if any(not isinstance(row,dict) for row in bundle['items']):
        raise ValueError('Each candidate must be an object')
    normalize_gaps(bundle.get('gaps',[]))
    return bundle
