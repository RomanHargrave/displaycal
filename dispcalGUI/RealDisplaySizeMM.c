#include "Python.h"

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <signal.h>
#ifdef NT
# include <windows.h>
# include <shlwapi.h>
#else
# include <unistd.h>
# include <sys/types.h>
# include <sys/stat.h>
#endif

#ifdef __APPLE__	/* Assume OSX Carbon */
# include <Carbon/Carbon.h>
# include <CoreServices/CoreServices.h>
# include <IOKit/Graphics/IOGraphicsLib.h>
#endif /* __APPLE__ */

#if defined(UNIX) && !defined(__APPLE__)
# include <X11/Xlib.h>
# include <X11/Xutil.h>
# include <X11/Xatom.h>
# include <X11/extensions/xf86vmode.h>
# include <X11/extensions/dpms.h>
# include <X11/extensions/Xinerama.h>
# include <X11/extensions/Xrandr.h>
# include <X11/extensions/dpms.h>
#endif /* UNIX */

#if defined(_MSC_VER)
# define DLL extern "C" __declspec(dllexport)
#else
# define DLL
#endif

#define errout stderr
#ifdef DEBUG
# define debug(xx)	fprintf(errout, xx )
# define debug2(xx)	fprintf xx
# define debugr(xx)	fprintf(errout, xx )
# define debugr2(xx)	fprintf xx
# define debugrr(xx)	fprintf(errout, xx )
# define debugrr2(xx)	fprintf xx
#else
# define debug(xx)
# define debug2(xx)
# define debugr(xx)
# define debugr2(xx)
# define debugrr(xx)
# define debugrr2(xx)
#endif


// START disppath

/* Structure to store infomation about possible displays */
typedef struct {
	char *name;			/* Display name */
	char *description;	/* Description of display */
	int sx,sy;			/* Displays offset in pixels */
	int sw,sh;			/* Displays width and height in pixels*/
#ifdef NT
	char monid[128];	/* Monitor ID */
	int prim;			/* NZ if primary display monitor */
#endif /* NT */
#ifdef __APPLE__
	CGDirectDisplayID ddid;
#endif /* __APPLE__ */
#if defined(UNIX) && !defined(__APPLE__)
	int screen;				/* Screen to select */
	int uscreen;			/* Underlying screen */
	int rscreen;			/* Underlying RAMDAC screen */
	Atom icc_atom;			/* ICC profile root atom for this display */
	unsigned char *edid;	/* 128 or 256 bytes of monitor EDID, NULL if none */
	int edid_len;			/* 128 or 256 */

#if RANDR_MAJOR == 1 && RANDR_MINOR >= 2
	/* Xrandr stuff - output is connected 1:1 to a display */
	RRCrtc crtc;				/* Associated crtc */
	RROutput output;			/* Associated output */
	Atom icc_out_atom;			/* ICC profile atom for this output */
#endif /* randr >= V 1.2 */
#endif /* UNIX */
} disppath;

// END disppath

void free_disppaths(disppath **paths);

/* ----------------------------------------------- */
/* Dealing with locating displays */

int callback_ddebug = 0;			/* Diagnostic global for get_displays() and get_a_display() */  

#ifdef NT

#define sleep(secs) Sleep((secs) * 1000)

static BOOL CALLBACK MonitorEnumProc(
  HMONITOR hMonitor,  /* handle to display monitor */
  HDC hdcMonitor,     /* NULL, because EnumDisplayMonitors hdc is NULL */
  LPRECT lprcMonitor, /* Virtual screen coordinates of this monitor */
  LPARAM dwData       /* Context data */
) {
	disppath ***pdisps = (disppath ***)dwData;
	disppath **disps = *pdisps;
	MONITORINFOEX pmi;
	int ndisps = 0;
	
	debugrr2((errout, "MonitorEnumProc() called with hMonitor = 0x%x\n",hMonitor));

	/* Get some more information */
	pmi.cbSize = sizeof(MONITORINFOEX);
	if (GetMonitorInfo(hMonitor, (MONITORINFO *)&pmi) == 0) {
		debugrr("get_displays failed GetMonitorInfo - ignoring display\n");
		return TRUE;
	}

	/* See if it seems to be a pseudo-display */
	if (strncmp(pmi.szDevice, "\\\\.\\DISPLAYV", 12) == 0) {
		debugrr("Seems to be invisible pseudo-display - ignoring it\n");
		return TRUE;
	}

	/* Add the display to the list */
	if (disps == NULL) {
		if ((disps = (disppath **)calloc(sizeof(disppath *), 1 + 1)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			return FALSE;
		}
	} else {
		/* Count current number on list */
		for (ndisps = 0; disps[ndisps] != NULL; ndisps++)
			;
		if ((disps = (disppath **)realloc(disps,
		                     sizeof(disppath *) * (ndisps + 2))) == NULL) {
			debugrr("get_displays failed on malloc\n");
			return FALSE;
		}
		disps[ndisps+1] = NULL;	/* End marker */
	}

	if ((disps[ndisps] = calloc(sizeof(disppath),1)) == NULL) {
		debugrr("get_displays failed on malloc\n");
		return FALSE;
	}

	if ((disps[ndisps]->name = strdup(pmi.szDevice)) == NULL) {
		debugrr("malloc failed\n");
		return FALSE;
	}
	disps[ndisps]->prim = (pmi.dwFlags & MONITORINFOF_PRIMARY) ? 1 : 0;

	disps[ndisps]->sx = lprcMonitor->left;
	disps[ndisps]->sy = lprcMonitor->top;
	disps[ndisps]->sw = lprcMonitor->right - lprcMonitor->left;
	disps[ndisps]->sh = lprcMonitor->bottom - lprcMonitor->top;

	disps[ndisps]->description = NULL;

	debugrr2((errout, "MonitorEnumProc() set initial monitor info: %d,%d %d,%d name '%s'\n",disps[ndisps]->sx,disps[ndisps]->sy,disps[ndisps]->sw,disps[ndisps]->sh, disps[ndisps]->name));

	*pdisps = disps;
	return TRUE;
}

/* Dynamically linked function support */

BOOL (WINAPI* pEnumDisplayDevices)(PVOID,DWORD,PVOID,DWORD) = NULL;

#if !defined(NTDDI_LONGHORN) || NTDDI_VERSION < NTDDI_LONGHORN

typedef enum {
	WCS_PROFILE_MANAGEMENT_SCOPE_SYSTEM_WIDE,
	WCS_PROFILE_MANAGEMENT_SCOPE_CURRENT_USER
} WCS_PROFILE_MANAGEMENT_SCOPE;

BOOL (WINAPI* pWcsAssociateColorProfileWithDevice)(WCS_PROFILE_MANAGEMENT_SCOPE,PCWSTR,PCWSTR) = NULL;
BOOL (WINAPI* pWcsDisassociateColorProfileFromDevice)(WCS_PROFILE_MANAGEMENT_SCOPE,PCWSTR,PCWSTR) = NULL;

#endif  /* NTDDI_VERSION < NTDDI_LONGHORN */

/* See if we can get the wanted function calls */
/* return nz if OK */
static int setup_dyn_calls() {
	static int dyn_inited = 0;

	if (dyn_inited == 0) {
		dyn_inited = 1;

		/* EnumDisplayDevicesA was left out of lib32.lib on earlier SDK's ... */
		pEnumDisplayDevices = (BOOL (WINAPI*)(PVOID,DWORD,PVOID,DWORD)) GetProcAddress(LoadLibrary("USER32"), "EnumDisplayDevicesA");
		if (pEnumDisplayDevices == NULL)
			dyn_inited = 0;

		/* Vista calls */
#if !defined(NTDDI_LONGHORN) || NTDDI_VERSION < NTDDI_LONGHORN
		pWcsAssociateColorProfileWithDevice = (BOOL (WINAPI*)(WCS_PROFILE_MANAGEMENT_SCOPE,PCWSTR,PCWSTR)) GetProcAddress(LoadLibrary("mscms"), "WcsAssociateColorProfileWithDevice");
		pWcsDisassociateColorProfileFromDevice = (BOOL (WINAPI*)(WCS_PROFILE_MANAGEMENT_SCOPE,PCWSTR,PCWSTR)) GetProcAddress(LoadLibrary("mscms"), "WcsDisassociateColorProfileFromDevice");
		/* These are checked individually */
#endif  /* NTDDI_VERSION < NTDDI_LONGHORN */
	}

	return dyn_inited;
}

/* Simple up conversion from char string to wchar string */
/* Return NULL if malloc fails */
/* ~~~ Note, should probably replace this with mbstowcs() ???? */
static unsigned short *char2wchar(char *s) {
	unsigned char *cp;
	unsigned short *w, *wp;

	if ((w = malloc(sizeof(unsigned short) * (strlen(s) + 1))) == NULL)
		return w;

	for (cp = (unsigned char *)s, wp = w; ; cp++, wp++) {
		*wp = *cp;		/* Zero extend */
		if (*cp == 0)
			break;
	}

	return w;
}

#endif /* NT */


#if defined(UNIX) && !defined(__APPLE__)
/* Hack to notice if the error handler has been triggered */
/* when a function doesn't return a value. */

int g_error_handler_triggered = 0;

/* A noop X11 error handler */
int null_error_handler(Display *disp, XErrorEvent *ev) {
	 g_error_handler_triggered = 1;
	return 0;
}
#endif	/* X11 */

/* Return pointer to list of disppath. Last will be NULL. */
/* Return NULL on failure. Call free_disppaths() to free up allocation */
disppath **get_displays() {
	disppath **disps = NULL;

#ifdef NT
	DISPLAY_DEVICE dd;
	char buf[200];
	int i, j;

	if (setup_dyn_calls() == 0) {
		debugrr("Dynamic linking to EnumDisplayDevices or Vista AssociateColorProfile failed\n");
		free_disppaths(disps);
		return NULL;
	}

	/* Create an initial list of monitors */
	/* (It might be better to call pEnumDisplayDevices(NULL, i ..) instead ??, */
	/* then we can use the StateFlags to distingish monitors not attached to the desktop etc.) */
	if (EnumDisplayMonitors(NULL, NULL, MonitorEnumProc, (LPARAM)&disps) == 0) {
		debugrr("EnumDisplayMonitors failed\n");
		free_disppaths(disps);
		return NULL;
	}

	/* Now locate detailed information about displays */
	for (i = 0; ; i++) {
		if (disps == NULL || disps[i] == NULL)
			break;

		dd.cb = sizeof(dd);

		debugrr2((errout, "get_displays about to get monitor information for %d\n",i));
		/* Get monitor information */
		for (j = 0; ;j++) {
			if ((*pEnumDisplayDevices)(disps[i]->name, j, &dd, 0) == 0) {
				debugrr2((errout,"EnumDisplayDevices failed on '%s' Mon = %d\n",disps[i]->name,j));
				if (j == 0) {
					strcpy(disps[i]->monid, "");		/* We won't be able to set a profile */
				}
				break;
			}
			if (callback_ddebug) {
				fprintf(errout,"Mon %d, name '%s'\n",j,dd.DeviceName);
				fprintf(errout,"Mon %d, string '%s'\n",j,dd.DeviceString);
				fprintf(errout,"Mon %d, flags 0x%x\n",j,dd.StateFlags);
				fprintf(errout,"Mon %d, id '%s'\n",j,dd.DeviceID);
				fprintf(errout,"Mon %d, key '%s'\n",j,dd.DeviceKey);
			}
			if (j == 0) {
				strcpy(disps[i]->monid, dd.DeviceID);
			}
		}

		sprintf(buf,"%s, at %d, %d, width %d, height %d%s",disps[i]->name+4,
	        disps[i]->sx, disps[i]->sy, disps[i]->sw, disps[i]->sh,
	        disps[i]->prim ? " (Primary Display)" : "");

		if ((disps[i]->description = strdup(buf)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			free_disppaths(disps);
			return NULL;
		}

		debugrr2((errout, "get_displays added description '%s' to display %d\n",disps[i]->description,i));

		/* Note that calling EnumDisplayDevices(NULL, j, ..) for the adapter can return other */
		/* information, such as the graphics card name, and additional state flags. */
		/* EnumDisplaySettings() can also be called to get information such as display depth etc. */
	}

#ifdef NEVER
	/* Explore adapter information */
	for (j = 0; ; j++) {
		/* Get adapater information */
		if ((*pEnumDisplayDevices)(NULL, j, &dd, 0) == 0)
			break;
		printf("Adapt %d, name '%s'\n",j,dd.DeviceName);
		printf("Adapt %d, string '%s'\n",j,dd.DeviceString);
		printf("Adapt %d, flags 0x%x\n",j,dd.StateFlags);
		printf("Adapt %d, id '%s'\n",j,dd.DeviceID);
		printf("Adapt %d, key '%s'\n",j,dd.DeviceKey);
	}
#endif /* NEVER */

#endif /* NT */

#ifdef __APPLE__
	/* Note :- some recent releases of OS X have a feature which */
	/* automatically adjusts the screen brigtness with ambient level. */
	/* We may have to find a way of disabling this during calibration and profiling. */
	/* See the "pset -g" command. */
	int i;
	CGDisplayErr dstat;
	CGDisplayCount dcount;		/* Number of display IDs */
	CGDirectDisplayID *dids;	/* Array of display IDs */

	if ((dstat = CGGetActiveDisplayList(0, NULL, &dcount)) != kCGErrorSuccess || dcount < 1) {
		debugrr("CGGetActiveDisplayList #1 returned error\n");
		return NULL;
	}
	if ((dids = (CGDirectDisplayID *)malloc(dcount * sizeof(CGDirectDisplayID))) == NULL) {
		debugrr("malloc of CGDirectDisplayID's failed\n");
		return NULL;
	}
	if ((dstat = CGGetActiveDisplayList(dcount, dids, &dcount)) != kCGErrorSuccess) {
		debugrr("CGGetActiveDisplayList #2 returned error\n");
		free(dids);
		return NULL;
	}

	/* Found dcount displays */
	debugrr2((errout,"Found %d screens\n",dcount));

	/* Allocate our list */
	if ((disps = (disppath **)calloc(sizeof(disppath *), dcount + 1)) == NULL) {
		debugrr("get_displays failed on malloc\n");
		free(dids);
		return NULL;
	}
	for (i = 0; i < dcount; i++) {
		if ((disps[i] = calloc(sizeof(disppath), 1)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			free_disppaths(disps);
			free(dids);
			return NULL;
		}
		disps[i]->ddid = dids[i];
	}

	/* Got displays, now figure out a description for each one */
	for (i = 0; i < dcount; i++) {
		CGRect dbound;				/* Bounding rectangle of chosen display */
		io_service_t dport;
		CFDictionaryRef ddr, pndr;
		CFIndex dcount;
		char *dp = NULL, desc[50];
		char buf[200];

		dbound = CGDisplayBounds(dids[i]);
		disps[i]->sx = dbound.origin.x;
		disps[i]->sy = dbound.origin.y;
		disps[i]->sw = dbound.size.width;
		disps[i]->sh = dbound.size.height;
			
		/* Try and get some information about the display */
		if ((dport = CGDisplayIOServicePort(dids[i])) == MACH_PORT_NULL) {
			debugrr("CGDisplayIOServicePort returned error\n");
			free_disppaths(disps);
			free(dids);
			return NULL;
		}

#ifdef NEVER
		{
			io_name_t name;
			if (IORegistryEntryGetName(dport, name) != KERN_SUCCESS) {
				debugrr("IORegistryEntryGetName returned error\n");
				free_disppaths(disps);
				free(dids);
				return NULL;
			}
			printf("Driver %d name = '%s'\n",i,name);
		}
#endif
		if ((ddr = IODisplayCreateInfoDictionary(dport, 0)) == NULL) {
			debugrr("IODisplayCreateInfoDictionary returned NULL\n");
			free_disppaths(disps);
			free(dids);
			return NULL;
		}
		if ((pndr = CFDictionaryGetValue(ddr, CFSTR(kDisplayProductName))) == NULL) {
			debugrr("CFDictionaryGetValue returned NULL\n");
			CFRelease(ddr);
			free_disppaths(disps);
			free(dids);
			return NULL;
		}
		if ((dcount = CFDictionaryGetCount(pndr)) > 0) {
			const void **keys;
			const void **values;
			int j;

			keys = (const void **)calloc(sizeof(void *), dcount);
			values = (const void **)calloc(sizeof(void *), dcount);
			if (keys == NULL || values == NULL) {
				if (keys != NULL)
					free(keys);
				if (values != NULL)
					free(values);
				debugrr("malloc failed\n");
				CFRelease(ddr);
				free_disppaths(disps);
				free(dids);
				return NULL;
			}
			CFDictionaryGetKeysAndValues(pndr, keys, values);
			for (j = 0; j < dcount; j++) {
				const char *k, *v;
				char kbuf[50], vbuf[50];
				k = CFStringGetCStringPtr(keys[j], kCFStringEncodingMacRoman);
				if (k == NULL) {
					if (CFStringGetCString(keys[j], kbuf, 50, kCFStringEncodingMacRoman))
						k = kbuf;
				}
				v = CFStringGetCStringPtr(values[j], kCFStringEncodingMacRoman);
				if (v == NULL) {
					if (CFStringGetCString(values[j], vbuf, 50, kCFStringEncodingMacRoman))
						v = vbuf;
				}
//printf("~1 got key %s and value %s\n",k,v);
				/* We're only grabing the english description... */
				if (k != NULL && v != NULL && strcmp(k, "en_US") == 0) {
					strncpy(desc, v, 49);
					desc[49] = '\000';
					dp = desc;
				}
			}
			free(keys);
			free(values);
		}
		CFRelease(ddr);

		if (dp == NULL) {
			strcpy(desc, "(unknown)");
			dp = desc;
		}
		sprintf(buf,"%s, at %d, %d, width %d, height %d%s",dp,
	        disps[i]->sx, disps[i]->sy, disps[i]->sw, disps[i]->sh,
	        CGDisplayIsMain(dids[i]) ? " (Primary Display)" : "");

		if ((disps[i]->name = strdup(dp)) == NULL
		 || (disps[i]->description = strdup(buf)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			free_disppaths(disps);
			free(dids);
			return NULL;
		}
	}

	free(dids);
#endif /* __APPLE__ */

#if defined(UNIX) && !defined(__APPLE__)
	int i, j, k;
	int defsix = 0;		/* default screen index */
	int dcount;			/* Number of screens */
	char *dname;
	char dnbuf[100];
	int evb = 0, erb = 0;
	int majv, minv;			/* Version */
	Display *mydisplay;
	int ndisps = 0;
	XineramaScreenInfo *xai = NULL;
	char desc1[100], desc2[200];

	/* There seems to be no way of getting the available displays */
	/* on an X11 system. Attempting to open them in sequence */
	/* takes too long. We just rely on the user supplying the */
	/* right display. We can enumerate screens though. */

	/* Open the base display, and then enumerate all the screens */
	if ((dname = getenv("DISPLAY")) != NULL) {
		char *pp;
		strncpy(dnbuf,dname,99); dnbuf[99] = '\000';
		if ((pp = strrchr(dnbuf, ':')) != NULL) {
			if ((pp = strchr(pp, '.')) == NULL)
				strcat(dnbuf,".0");
			else  {
				if (pp[1] == '\000')
					strcat(dnbuf,"0");
				else {
					pp[1] = '0';
					pp[2] = '\000';
				}
			}
		}
	} else
		strcpy(dnbuf,":0.0");

	if ((mydisplay = XOpenDisplay(dnbuf)) == NULL) {
		debugrr2((errout, "failed to open display '%s'\n",dnbuf));
		return NULL;
	}

#if RANDR_MAJOR == 1 && RANDR_MINOR >= 2 && !defined(DISABLE_RANDR)
	/* Use Xrandr 1.2 if it's available, and if it's not disabled */
	if (getenv("ARGYLL_IGNORE_XRANDR1_2") == NULL
	 && XRRQueryExtension(mydisplay, &evb, &erb) != 0
	 && XRRQueryVersion(mydisplay, &majv, &minv)
	 && majv == 1 && minv >= 2) {

		if (XSetErrorHandler(null_error_handler) == 0) {
			debugrr("get_displays failed on XSetErrorHandler\n");
			XCloseDisplay(mydisplay);
			free_disppaths(disps);
			return NULL;
		}

		dcount = ScreenCount(mydisplay);

		/* Go through all the screens */
		for (i = 0; i < dcount; i++) {
			XRRScreenResources *scrnres;
			int jj;		/* Screen index */

			if ((scrnres = XRRGetScreenResources(mydisplay, RootWindow(mydisplay,i))) == NULL) {
				debugrr("XRRGetScreenResources failed\n");
				XCloseDisplay(mydisplay);
				free_disppaths(disps);
				return NULL;
			}

			/* Look at all the screens outputs */
			for (jj = j = 0; j < scrnres->noutput; j++) {
				XRROutputInfo *outi;
				XRRCrtcInfo *crtci;
	
				if ((outi = XRRGetOutputInfo(mydisplay, scrnres, scrnres->outputs[j])) == NULL) {
					debugrr("XRRGetOutputInfo failed\n");
					XRRFreeScreenResources(scrnres);
					XCloseDisplay(mydisplay);
					free_disppaths(disps);
					return NULL;
				}
	
				if (outi->connection == RR_Disconnected||
					outi->crtc == None) {
					continue;
				}

				/* Check that the VideoLUT's are accessible */
				{
					XRRCrtcGamma *crtcgam;
			
					debugrr("Checking XRandR 1.2 VideoLUT access\n");
					if ((crtcgam = XRRGetCrtcGamma(mydisplay, outi->crtc)) == NULL
					 || crtcgam->size == 0) {
						
						if (crtcgam != NULL)
							XRRFreeGamma(crtcgam);
						free_disppaths(disps);
						disps = NULL;
						j = scrnres->noutput;
						i = dcount;
						continue;				/* Abort XRandR 1.2 */
					}
				}
#ifdef NEVER
				{
					Atom *oprops;
					int noprop;

					/* Get a list of the properties of the output */
					oprops = XRRListOutputProperties(mydisplay, scrnres->outputs[j], &noprop);

					printf("num props = %d\n", noprop);
					for (k = 0; k < noprop; k++) {
						printf("%d: atom 0x%x, name = '%s'\n", k, oprops[k], XGetAtomName(mydisplay, oprops[k]));
					}
				}
#endif /* NEVER */

				if ((crtci = XRRGetCrtcInfo(mydisplay, scrnres, outi->crtc)) != NULL) {
					char *pp;

					/* Add the output to the list */
					if (disps == NULL) {
						if ((disps = (disppath **)calloc(sizeof(disppath *), 1 + 1)) == NULL) {
							debugrr("get_displays failed on malloc\n");
							XRRFreeCrtcInfo(crtci);
							XRRFreeScreenResources(scrnres);
							XCloseDisplay(mydisplay);
							return NULL;
						}
					} else {
						if ((disps = (disppath **)realloc(disps,
						                     sizeof(disppath *) * (ndisps + 2))) == NULL) {
							debugrr("get_displays failed on malloc\n");
							XRRFreeCrtcInfo(crtci);
							XRRFreeScreenResources(scrnres);
							XCloseDisplay(mydisplay);
							return NULL;
						}
						disps[ndisps+1] = NULL;	/* End marker */
					}
					/* ndisps is current display we're filling in */
					if ((disps[ndisps] = calloc(sizeof(disppath),1)) == NULL) {
						debugrr("get_displays failed on malloc\n");
						XRRFreeCrtcInfo(crtci);
						XRRFreeScreenResources(scrnres);
						XCloseDisplay(mydisplay);
						free_disppaths(disps);
						return NULL;
					}

					disps[ndisps]->screen = i;
					disps[ndisps]->uscreen = i;
					disps[ndisps]->rscreen = i;
					disps[ndisps]->sx = crtci->x;
					disps[ndisps]->sy = crtci->y;
					disps[ndisps]->sw = crtci->width;
					disps[ndisps]->sh = crtci->height;
					disps[ndisps]->crtc = outi->crtc;				/* XID of crtc */
					disps[ndisps]->output = scrnres->outputs[j];	/* XID of output */		

					sprintf(desc1,"Screen %d, Output %s",ndisps+1,outi->name);
					sprintf(desc2,"%s at %d, %d, width %d, height %d",desc1,
				        disps[ndisps]->sx, disps[ndisps]->sy, disps[ndisps]->sw, disps[ndisps]->sh);

					/* See if it is a clone */
					for (k = 0; k < ndisps; k++) {
						if (disps[k]->crtc == disps[ndisps]->crtc) {
							sprintf(desc1, "[ Clone of %d ]",k+1);
							strcat(desc2, desc1);
						}
					}
					if ((disps[ndisps]->description = strdup(desc2)) == NULL) {
						debugrr("get_displays failed on malloc\n");
						XRRFreeCrtcInfo(crtci);
						XRRFreeScreenResources(scrnres);
						XCloseDisplay(mydisplay);
						free_disppaths(disps);
						return NULL;
					}
	
					/* Form the display name */
					if ((pp = strrchr(dnbuf, ':')) != NULL) {
						if ((pp = strchr(pp, '.')) != NULL) {
							sprintf(pp,".%d",i);
						}
					}
					if ((disps[ndisps]->name = strdup(dnbuf)) == NULL) {
						debugrr("get_displays failed on malloc\n");
						XRRFreeCrtcInfo(crtci);
						XRRFreeScreenResources(scrnres);
						XCloseDisplay(mydisplay);
						free_disppaths(disps);
						return NULL;
					}
					debugrr2((errout, "Display %d name = '%s'\n",ndisps,disps[ndisps]->name));
	
					/* Create the X11 root atom of the default screen */
					/* that may contain the associated ICC profile */
					/* (The _%d variant will probably break with non-Xrandr */
					/* aware software if Xrandr is configured to have more than */
					/* a single virtual screen.) */
					if (jj == 0)
						strcpy(desc1, "_ICC_PROFILE");
					else
						sprintf(desc1, "_ICC_PROFILE_%d",jj);

					if ((disps[ndisps]->icc_atom = XInternAtom(mydisplay, desc1, False)) == None)
						error("Unable to intern atom '%s'",desc1);

					/* Create the atom of the output that may contain the associated ICC profile */
					if ((disps[ndisps]->icc_out_atom = XInternAtom(mydisplay, "_ICC_PROFILE", False)) == None)
						error("Unable to intern atom '%s'","_ICC_PROFILE");
		
					/* Grab the EDID from the output */
					{
						Atom edid_atom, ret_type;
						int ret_format;
						long ret_len = 0, ret_togo;
						unsigned char *atomv = NULL;
						int ii;
						char *keys[] = {		/* Possible keys that may be used */
							"EDID_DATA",
							"EDID",
							""
						};

						/* Try each key in turn */
						for (ii = 0; keys[ii][0] != '\000'; ii++) {
							/* Get the atom for the EDID data */
							if ((edid_atom = XInternAtom(mydisplay, keys[ii], True)) == None) {
								debugrr2((errout, "Unable to intern atom '%s'\n",keys[ii]));
								/* Try the next key */
							} else {

								/* Get the EDID_DATA */
								if (XRRGetOutputProperty(mydisplay, scrnres->outputs[j], edid_atom,
								            0, 0x7ffffff, False, False, XA_INTEGER, 
   		                            &ret_type, &ret_format, &ret_len, &ret_togo, &atomv) == Success
							            && (ret_len == 128 || ret_len == 256)) {
									if ((disps[ndisps]->edid = malloc(sizeof(unsigned char) * ret_len)) == NULL) {
										debugrr("get_displays failed on malloc\n");
										XRRFreeCrtcInfo(crtci);
										XRRFreeScreenResources(scrnres);
										XCloseDisplay(mydisplay);
										free_disppaths(disps);
										return NULL;
									}
									memcpy(disps[ndisps]->edid, atomv, ret_len);
									disps[ndisps]->edid_len = ret_len;
									XFree(atomv);
									debugrr2((errout, "Got EDID for display\n"));
									break;
								}
								/* Try the next key */
							}
						}
						if (keys[ii][0] == '\000')
							debugrr2((errout, "Failed to get EDID for display\n"));
					}
		
					jj++;			/* Next enabled index */
					ndisps++;		/* Now it's number of displays */
					XRRFreeCrtcInfo(crtci);
				}
				XRRFreeOutputInfo(outi);
			}
	
			XRRFreeScreenResources(scrnres);
		}
		XSetErrorHandler(NULL);
		defsix = DefaultScreen(mydisplay);
	}
#endif /* randr >= V 1.2 */

	if (disps == NULL) {	/* Use Older style identification */
		debugrr("get_displays checking for Xinerama\n");

		if (XSetErrorHandler(null_error_handler) == 0) {
			debugrr("get_displays failed on XSetErrorHandler\n");
			XCloseDisplay(mydisplay);
			return NULL;
		}

		if (XineramaQueryExtension(mydisplay, &evb, &erb) != 0
		 && XineramaIsActive(mydisplay)) {

			xai = XineramaQueryScreens(mydisplay, &dcount);

			if (xai == NULL || dcount == 0) {
				debugrr("XineramaQueryScreens failed\n");
				XCloseDisplay(mydisplay);
				return NULL;
			}
			defsix = 0;
		} else {
			dcount = ScreenCount(mydisplay);
			defsix = DefaultScreen(mydisplay);
		}

		/* Allocate our list */
		if ((disps = (disppath **)calloc(sizeof(disppath *), dcount + 1)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			XCloseDisplay(mydisplay);
			return NULL;
		}
		for (i = 0; i < dcount; i++) {
			if ((disps[i] = calloc(sizeof(disppath), 1)) == NULL) {
				debugrr("get_displays failed on malloc\n");
				free_disppaths(disps);
				XCloseDisplay(mydisplay);
				return NULL;
			}
		}

		/* Create a description for each screen */
		for (i = 0; i < dcount; i++) {
		    XF86VidModeMonitor monitor;
			int evb = 0, erb = 0;
			char *pp;

			/* Form the display name */
			if ((pp = strrchr(dnbuf, ':')) != NULL) {
				if ((pp = strchr(pp, '.')) != NULL) {
					sprintf(pp,".%d",i);
				}
			}
			if ((disps[i]->name = strdup(dnbuf)) == NULL) {
				debugrr("get_displays failed on malloc\n");
				free_disppaths(disps);
				XCloseDisplay(mydisplay);
				return NULL;
			}
	
			debugrr2((errout, "Display %d name = '%s'\n",i,disps[i]->name));
			if (xai != NULL) {					/* Xinerama */
				disps[i]->screen = 0;			/* We are asuming Xinerame creates a single virtual screen */
				disps[i]->uscreen = i;			/* We are assuming xinerama lists screens in the same order */
				disps[i]->rscreen = i;
				disps[i]->sx = xai[i].x_org;
				disps[i]->sy = xai[i].y_org;
				disps[i]->sw = xai[i].width;
				disps[i]->sh = xai[i].height;
			} else {
				disps[i]->screen = i;
				disps[i]->uscreen = i;
				disps[i]->rscreen = i;
				disps[i]->sx = 0;			/* Must be 0 */
				disps[i]->sy = 0;
				disps[i]->sw = DisplayWidth(mydisplay, disps[i]->screen);
				disps[i]->sh = DisplayHeight(mydisplay, disps[i]->screen);
			}

			/* Create the X11 root atom of the default screen */
			/* that may contain the associated ICC profile */
			if (disps[i]->uscreen == 0)
				strcpy(desc1, "_ICC_PROFILE");
			else
				sprintf(desc1, "_ICC_PROFILE_%d",disps[i]->uscreen);

			if ((disps[i]->icc_atom = XInternAtom(mydisplay, desc1, False)) == None)
				error("Unable to intern atom '%s'",desc1);

			/* See if we can locate the EDID of the monitor for this screen */
			for (j = 0; j < 2; j++) { 
				char edid_name[50];
				Atom edid_atom, ret_type;
				int ret_format = 8;
				long ret_len, ret_togo;
				unsigned char *atomv = NULL;

				if (disps[i]->uscreen == 0) {
					if (j == 0)
						strcpy(edid_name,"XFree86_DDC_EDID1_RAWDATA");
					else
						strcpy(edid_name,"XFree86_DDC_EDID2_RAWDATA");
				} else {
					if (j == 0)
						sprintf(edid_name,"XFree86_DDC_EDID1_RAWDATA_%d",disps[i]->uscreen);
					else
						sprintf(edid_name,"XFree86_DDC_EDID2_RAWDATA_%d",disps[i]->uscreen);
				}

				if ((edid_atom = XInternAtom(mydisplay, edid_name, True)) == None)
					continue;
				if (XGetWindowProperty(mydisplay, RootWindow(mydisplay, disps[i]->uscreen), edid_atom,
				            0, 0x7ffffff, False, XA_INTEGER, 
				            &ret_type, &ret_format, &ret_len, &ret_togo, &atomv) == Success
				            && (ret_len == 128 || ret_len == 256)) {
					if ((disps[i]->edid = malloc(sizeof(unsigned char) * ret_len)) == NULL) {
						debugrr("get_displays failed on malloc\n");
						free_disppaths(disps);
						XCloseDisplay(mydisplay);
						return NULL;
					}
					memcpy(disps[i]->edid, atomv, ret_len);
					disps[i]->edid_len = ret_len;
					XFree(atomv);
					debugrr2((errout, "Got EDID for display\n"));
					break;
				} else {
					debugrr2((errout, "Failed to get EDID for display\n"));
				}
			}

			if (XF86VidModeQueryExtension(mydisplay, &evb, &erb) != 0) {
				/* Some propietary multi-screen drivers (ie. TwinView & MergeFB) */
				/* don't implement the XVidMode extension properly. */
				monitor.model = NULL;
				if (XF86VidModeGetMonitor(mydisplay, disps[i]->uscreen, &monitor) != 0
				 && monitor.model != NULL && monitor.model[0] != '\000')
					sprintf(desc1, "%s",monitor.model);
				else
					sprintf(desc1,"Screen %d",i+1);
			} else
				sprintf(desc1,"Screen %d",i+1);

			sprintf(desc2,"%s at %d, %d, width %d, height %d",desc1,
		        disps[i]->sx, disps[i]->sy, disps[i]->sw, disps[i]->sh);
			if ((disps[i]->description = strdup(desc2)) == NULL) {
				debugrr("get_displays failed on malloc\n");
				free_disppaths(disps);
				XCloseDisplay(mydisplay);
				return NULL;
			}
		}
		XSetErrorHandler(NULL);
	}

	/* Put the screen given by the display name at the top */
	{
		disppath *tdispp;
		tdispp = disps[defsix];
		disps[defsix] = disps[0];
		disps[0] = tdispp;
	}

	if (xai != NULL)
		XFree(xai);

	XCloseDisplay(mydisplay);

#endif /* UNIX X11 */

	return disps;
}

// END get_displays

/* Free a whole list of display paths */
void free_disppaths(disppath **disps) {
	if (disps != NULL) {
		int i;
		for (i = 0; ; i++) {
			if (disps[i] == NULL)
				break;

			if (disps[i]->name != NULL)
				free(disps[i]->name);
			if (disps[i]->description != NULL)
				free(disps[i]->description);
#if defined(UNIX) && !defined(__APPLE__)
			if (disps[i]->edid != NULL)
				free(disps[i]->edid);
#endif
			free(disps[i]);
		}
		free(disps);
	}
}

// START get_a_display

disppath *get_a_display(int ix) {
	disppath **paths, *rv = NULL;
	int i;

	if ((paths = get_displays()) == NULL)
		return NULL;

	for (i = 0; ;i++) {
		if (paths[i] == NULL) {
			free_disppaths(paths);
			return NULL;
		}
		if (i == ix)
			break;
	}
	if ((rv = malloc(sizeof(disppath))) == NULL) {
		debugrr("get_a_display failed malloc\n");
		free_disppaths(paths);
		return NULL;
	}
	*rv = *paths[i];		/* Structure copy */
	if ((rv->name = strdup(paths[i]->name)) == NULL) {
		debugrr("get_displays failed on malloc\n");
		free(rv->description);
		free(rv);
		free_disppaths(paths);
		return NULL;
	}
	if ((rv->description = strdup(paths[i]->description)) == NULL) {
		debugrr("get_displays failed on malloc\n");
		free(rv);
		free_disppaths(paths);
		return NULL;
	}
#if defined(UNIX) && !defined(__APPLE__)
	if (paths[i]->edid != NULL) {
		if ((rv->edid = malloc(sizeof(unsigned char) * paths[i]->edid_len)) == NULL) {
			debugrr("get_displays failed on malloc\n");
			free(rv);
			free_disppaths(paths);
			return NULL;
		}
		rv->edid_len = paths[i]->edid_len;
		memcpy(rv->edid, paths[i]->edid, rv->edid_len );
	}
#endif
	free_disppaths(paths);
	return rv;
}
// END get_a_display

// MAIN

typedef struct {
	int width_mm, height_mm;
} size_mm;

static size_mm real_screen_size_mm(int ix) {
	size_mm size_mm;
	disppath *disp = NULL;
#ifdef NT
	HDC hdc = NULL;
#endif
#ifdef __APPLE__
	CGSize sz;				/* Display size in mm */
#endif
#if defined(UNIX) && !defined(__APPLE__)
	char *pp, *bname;		/* base display name */
	Display *mydisplay;
	int myscreen;			/* Usual or virtual screen with Xinerama */
#endif

	size_mm.width_mm = 0;
	size_mm.height_mm = 0;

	disp = get_a_display(ix);

	if (disp == NULL) return size_mm;

#ifdef NT
	hdc = CreateDC(disp->name, NULL, NULL, NULL);
	if (hdc == NULL) return size_mm;
	size_mm.width_mm = GetDeviceCaps(hdc, HORZSIZE);
	size_mm.height_mm = GetDeviceCaps(hdc, VERTSIZE);
#endif
#ifdef __APPLE__
	sz = CGDisplayScreenSize(disp->ddid);
	size_mm.width_mm = sz.width;
	size_mm.height_mm = sz.height;
#endif
#if defined(UNIX) && !defined(__APPLE__)
	/* Create the base display name (in case of Xinerama, XRandR) */
	if ((bname = strdup(disp->name)) == NULL) return size_mm;
	if ((pp = strrchr(bname, ':')) != NULL) {
		if ((pp = strchr(pp, '.')) != NULL) {
			sprintf(pp,".%d",disp->screen);
		}
	}

	/* open the display */
	mydisplay = XOpenDisplay(bname);
	if(!mydisplay) {
		debugr2((errout,"Unable to open display '%s'\n",bname));
		free(bname);
		return size_mm;
	}
	free(bname);
	debugr("Opened display OK\n");

	myscreen = disp->screen;
	
	size_mm.width_mm = DisplayWidthMM(mydisplay, myscreen);
	size_mm.height_mm = DisplayHeightMM(mydisplay, myscreen);
#endif

	return size_mm;
}

static PyObject *
RealDisplaySizeMM(PyObject *self, PyObject *args)
{
	int ix;
	size_mm size_mm;
	
	if (!PyArg_ParseTuple(args, "i", &ix)) ix = 0;

	size_mm = real_screen_size_mm(ix);

	return Py_BuildValue("(i,i)", size_mm.width_mm, size_mm.height_mm);
}

static PyMethodDef RealDisplaySizeMM_methods[] = {
	{"RealDisplaySizeMM", RealDisplaySizeMM, METH_VARARGS, "RealDisplaySizeMM(int displayNum = 0)\nReturn the size (in mm) of a given display."},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initRealDisplaySizeMM(void)
{
	Py_InitModule("RealDisplaySizeMM", RealDisplaySizeMM_methods);
}
