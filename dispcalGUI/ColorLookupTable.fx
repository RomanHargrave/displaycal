// Color Look Up Table Shader 1.0 ==============================================

// Configuration ---------------------------------------------------------------

// Key to toggle CLUT on or off. See MSDN, "Virtual-Key Codes",
// msdn.microsoft.com/library/windows/desktop/dd375731%28v=vs.85%29.aspx
// for a list of key codes.
#define CLUT_TOGGLEKEY	0x24	// 0x24 = HOME key

// END Configuration -----------------------------------------------------------

#pragma message "\nColor Look Up Table Shader 1.0\n"
#pragma reshade showtogglemessage

texture2D texColor : COLOR;

texture texCLUT < string source = "ColorLookupTable.png"; >
{
	Width = ${WIDTH};
	Height = ${HEIGHT};
	Format = ${FORMAT};
};

sampler2D samplerColor
{
	Texture = texColor;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

sampler2D samplerCLUT
{
	Texture = texCLUT;
	MinFilter = LINEAR;
	MagFilter = LINEAR;
	MipFilter = LINEAR;
	AddressU = Clamp;
	AddressV = Clamp;
};

void VS_ColorLookupTable(in uint id : SV_VertexID,
						 out float4 position : SV_Position,
						 out float2 texcoord : TEXCOORD0)
{
	texcoord.x = (id == 2) ? 2.0 : 0.0;
	texcoord.y = (id == 1) ? 2.0 : 0.0;
	position = float4(texcoord * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
}

float4 PS_ColorLookupTable(in float2 texcoord : TEXCOORD0) : COLOR 
{
	float4 color = tex2D(samplerColor, texcoord.xy);

	float3 CLUTcolor = 0.0;	
	float2 GridSize = float2(${GRID_X}, ${GRID_Y});
	float3 coord3D = saturate(color.xyz);
	coord3D.z *= ${CLUT_MAXINDEX};
	float shift = floor(coord3D.z);
	coord3D.xy = coord3D.xy * ${CLUT_MAXINDEX} * GridSize + 0.5 * GridSize;
	coord3D.x += shift * ${GRID_Y};
	CLUTcolor.xyz = lerp(tex2D(samplerCLUT, coord3D.xy).xyz,
						 tex2D(samplerCLUT, coord3D.xy + float2(GridSize.y, 0)).xyz,
						 coord3D.z - shift);
	color.xyz = lerp(color.xyz, CLUTcolor.xyz, 1.0);

	return color;
}

technique ColorLookupTable < bool enabled = 1; toggle = CLUT_TOGGLEKEY; >
{
	pass
	{
		VertexShader = VS_ColorLookupTable;
		PixelShader = PS_ColorLookupTable;
	}
}
