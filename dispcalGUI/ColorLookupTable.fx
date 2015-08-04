// Color Look Up Table Shader 1.0 ==============================================

// Configuration ---------------------------------------------------------------

#define CLUT_ENABLED	1

// Key to toggle CLUT on or off. See MSDN, "Virtual-Key Codes",
// msdn.microsoft.com/library/windows/desktop/dd375731%28v=vs.85%29.aspx
// for a list of key codes.
#define CLUT_TOGGLEKEY	0x24	// 0x24 = HOME key

// END Configuration -----------------------------------------------------------

#pragma message "\nColor Look Up Table Shader ${VERSION}\n"
#pragma reshade showtogglemessage

texture2D ColorLookupTable_texColor : COLOR;

texture ColorLookupTable_texCLUT < string source = "ColorLookupTable.png"; >
{
	Width = ${WIDTH};
	Height = ${HEIGHT};
	Format = ${FORMAT};
};

sampler2D ColorLookupTable_samplerColor
{
	Texture = ColorLookupTable_texColor;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

sampler2D ColorLookupTable_samplerCLUT
{
	Texture = ColorLookupTable_texCLUT;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

void ColorLookupTable_VS(in uint id : SV_VertexID,
						 out float4 position : SV_Position,
						 out float2 texcoord : TEXCOORD0)
{
	texcoord.x = (id == 2) ? 2.0 : 0.0;
	texcoord.y = (id == 1) ? 2.0 : 0.0;
	position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float4 ColorLookupTable_PS(in float2 texcoord : TEXCOORD0) : COLOR 
{
	float4 color = tex2D(ColorLookupTable_samplerColor, texcoord.xy);

	float3 CLUTcolor = 0.0;	
	float2 CLUTgrid = float2(${GRID_X}, ${GRID_Y});
	float3 CLUTcoord = saturate(color.xyz);
	CLUTcoord.z *= ${CLUT_MAXINDEX};
	float shift = floor(CLUTcoord.z);
	CLUTcoord.xy = CLUTcoord.xy * ${CLUT_MAXINDEX} * CLUTgrid + 0.5 * CLUTgrid;
	CLUTcoord.x += shift * ${GRID_Y};
	CLUTcolor.xyz = lerp(tex2D(ColorLookupTable_samplerCLUT, CLUTcoord.xy).xyz,
						 tex2D(ColorLookupTable_samplerCLUT, CLUTcoord.xy + float2(CLUTgrid.y, 0)).xyz,
						 CLUTcoord.z - shift);
	color.xyz = lerp(color.xyz, CLUTcolor.xyz, 1.0);

	return color;
}

technique ColorLookupTable < bool enabled = CLUT_ENABLED; toggle = CLUT_TOGGLEKEY; >
{
	pass
	{
		VertexShader = ColorLookupTable_VS;
		PixelShader = ColorLookupTable_PS;
	}
}
